from __future__ import annotations

import re
import asyncio
from collections import defaultdict
from datetime import datetime
from typing import Any

from .notion_repository import NotionRepository
from .schemas import TestCaseDashboardResponse, TestCasePageStats, TestCasePlatformStats, TestCaseStatusCounts


DEFAULT_TEST_CASE_SOURCE_URL = (
    "https://app.notion.com/p/3a773fbd195180af93ddc50099a7df6c"
    "?v=dae73fbd1951832d8e5908953dad8da6&source=copy_link"
)
DEFAULT_TEST_CASE_SOURCE_URLS = (DEFAULT_TEST_CASE_SOURCE_URL,)

PLATFORM_ALIASES = {
    "AOS": ("AOS", "Android", "ANDROID", "안드로이드"),
    "iOS": ("iOS", "IOS", "iPhone", "아이폰", "아이오에스"),
    "BO": ("BO", "Back Office", "BackOffice", "Admin", "관리자"),
    "Web": ("Web", "WEB", "웹"),
}
OS_COLUMN_CANDIDATES = ("OS", "Platform", "플랫폼", "운영체제", "환경", "Device OS")
RESULT_COLUMN_CANDIDATES = ("결과", "Result", "테스트 결과", "Test Result", "검증 결과", "진행 결과", "Status", "상태")
TC_TITLE_CANDIDATES = ("TC-ID", "TC ID", "Test Case", "Test Item", "테스트 케이스", "테스트케이스", "항목", "제목", "Name")


class TestCaseRepository:
    def __init__(self, notion: NotionRepository):
        self.notion = notion
        self._traversal_semaphore = asyncio.Semaphore(6)

    async def dashboard(
        self,
        source_url: str = DEFAULT_TEST_CASE_SOURCE_URL,
        source_urls: tuple[str, ...] = DEFAULT_TEST_CASE_SOURCE_URLS,
    ) -> TestCaseDashboardResponse:
        rows = []
        seen_row_keys = set()
        for current_source_url in source_urls or (source_url,):
            source_id = parse_notion_id(current_source_url)
            page_name = source_page_name(current_source_url) or "테스트케이스"
            for row in await self._collect_rows(source_id, page_name):
                key = row_identity(row)
                if key in seen_row_keys:
                    continue
                seen_row_keys.add(key)
                rows.append(row)
        if not rows:
            raise RuntimeError("테스트케이스 데이터를 찾지 못했습니다. Notion integration 공유 또는 원본 테스트케이스 DB 링크를 확인하세요.")
        page_buckets: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in rows:
            page_buckets[row.get("_page_name") or "테스트케이스"].append(row)

        pages = [self._page_stats(page_name, page_rows) for page_name, page_rows in sorted(page_buckets.items())]
        platform_totals: dict[str, TestCaseStatusCounts] = defaultdict(TestCaseStatusCounts)
        summary = TestCaseStatusCounts()
        for page in pages:
            add_counts(summary, page)
            for platform in page.platforms:
                add_counts(platform_totals[platform.platform], platform)

        return TestCaseDashboardResponse(
            source_url=source_url,
            updated_at=datetime.now(self.notion.settings.tz),
            summary=finalize_counts(summary),
            platforms=[
                TestCasePlatformStats(platform=platform, **finalize_counts(counts).model_dump())
                for platform, counts in sorted(platform_totals.items(), key=lambda item: platform_sort_key(item[0]))
            ],
            pages=pages,
        )

    async def diagnose(self, source_url: str = DEFAULT_TEST_CASE_SOURCE_URL) -> dict[str, Any]:
        source_id = parse_notion_id(source_url)
        result: dict[str, Any] = {
            "source_id": source_id,
            "database": {},
            "children": {},
        }
        try:
            pages = await self._query_database(source_id)
            result["database"] = {
                "ok": True,
                "row_count": len(pages),
                "sample_property_names": list((pages[0].get("properties") or {}).keys()) if pages else [],
                "detected_test_rows": sum(1 for page in pages if looks_like_test_case_row(page_to_row(page))),
            }
        except Exception as exc:
            result["database"] = {"ok": False, "error_type": type(exc).__name__, "error": safe_error(exc)}

        try:
            children = await self._block_children(source_id)
            child_database_ids = [block.get("id", "") for block in children if block.get("type") == "child_database"]
            result["children"] = {
                "ok": True,
                "count": len(children),
                "types": count_values(block.get("type", "") for block in children),
                "child_database_count": len(child_database_ids),
                "has_children_count": sum(1 for block in children if block.get("has_children")),
                "sample": [
                    {
                        "type": block.get("type", ""),
                        "has_children": bool(block.get("has_children")),
                        "title": block_title(block),
                    }
                    for block in children[:20]
                ],
            }
            child_database_summaries = []
            for database_id in child_database_ids[:5]:
                try:
                    pages = await self._query_database(database_id)
                    child_database_summaries.append(
                        {
                            "row_count": len(pages),
                            "sample_property_names": list((pages[0].get("properties") or {}).keys()) if pages else [],
                            "detected_test_rows": sum(1 for page in pages if looks_like_test_case_row(page_to_row(page))),
                        }
                    )
                except Exception as exc:
                    child_database_summaries.append({"error_type": type(exc).__name__, "error": safe_error(exc)})
            result["children"]["child_databases"] = child_database_summaries
        except Exception as exc:
            result["children"] = {"ok": False, "error_type": type(exc).__name__, "error": safe_error(exc)}
        return result

    async def _collect_rows(
        self,
        notion_id: str,
        page_name: str,
        depth: int = 7,
        visited: set[str] | None = None,
        try_database: bool = True,
    ) -> list[dict[str, str]]:
        if depth <= 0:
            return []
        notion_id = normalize_notion_id(notion_id)
        visited = visited or set()
        if notion_id in visited:
            return []
        visited.add(notion_id)

        rows = []
        if try_database:
            try:
                pages = await self._query_database(notion_id)
                for page in pages:
                    row = page_to_row(page)
                    row["_page_name"] = page_name
                    row["_row_id"] = page.get("id", "")
                    if looks_like_test_case_row(row):
                        rows.append(row)
                if rows:
                    return rows
                if pages:
                    return await self._collect_page_rows(pages, page_name, depth, visited)
            except Exception:
                pass

        try:
            blocks = await self._block_children(notion_id)
        except Exception:
            return rows

        for block in blocks:
            block_type = block.get("type")
            block_id = block.get("id", "")
            if block_type == "child_database":
                title = (block.get("child_database") or {}).get("title") or page_name
                try:
                    database_pages = await self._query_database(block_id)
                except Exception:
                    database_pages = []
                database_rows = []
                for page in database_pages:
                    row = page_to_row(page)
                    row["_page_name"] = title
                    row["_row_id"] = page.get("id", "")
                    if looks_like_test_case_row(row):
                        database_rows.append(row)
                if database_rows:
                    rows.extend(database_rows)
                else:
                    rows.extend(await self._collect_page_rows(database_pages, title, depth, visited))
            elif block_type == "child_page":
                title = (block.get("child_page") or {}).get("title") or page_name
                rows.extend(await self._collect_rows(block_id, title, depth - 1, visited))
            elif block_type == "table":
                rows.extend(await self._table_rows(block_id, page_name))
            elif block_type == "link_to_page":
                link = block.get("link_to_page") or {}
                linked_id = link.get("page_id") or link.get("database_id")
                if linked_id:
                    rows.extend(await self._collect_rows(linked_id, page_name, depth - 1, visited))
            for linked_id in linked_notion_ids_from_block(block):
                linked_page_name = linked_page_name_from_block(block, page_name)
                rows.extend(await self._collect_rows(linked_id, linked_page_name, depth - 1, visited))
            if block.get("has_children"):
                rows.extend(await self._collect_rows(block_id, page_name, depth - 1, visited, try_database=False))
        return rows

    async def _collect_page_rows(
        self,
        pages: list[dict[str, Any]],
        fallback_page_name: str,
        depth: int,
        visited: set[str],
    ) -> list[dict[str, str]]:
        async def collect(page: dict[str, Any]) -> list[dict[str, str]]:
            async with self._traversal_semaphore:
                child_page_name = page_name_from_page(page) or fallback_page_name
                return await self._collect_rows(page.get("id", ""), child_page_name, depth - 1, visited, try_database=False)

        chunks = await asyncio.gather(*(collect(page) for page in pages if page.get("id")), return_exceptions=True)
        rows: list[dict[str, str]] = []
        for chunk in chunks:
            if isinstance(chunk, Exception):
                continue
            rows.extend(chunk)
        return rows

    async def _query_database(self, database_id: str) -> list[dict[str, Any]]:
        pages: list[dict[str, Any]] = []
        cursor = None
        while True:
            payload: dict[str, Any] = {"page_size": 100}
            if cursor:
                payload["start_cursor"] = cursor
            data = await self.notion._request("POST", f"/databases/{database_id}/query", json=payload)
            pages.extend(data.get("results", []))
            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")
            if not cursor:
                break
        return pages

    async def _block_children(self, block_id: str) -> list[dict[str, Any]]:
        children: list[dict[str, Any]] = []
        cursor = None
        while True:
            path = f"/blocks/{block_id}/children?page_size=100"
            if cursor:
                path += f"&start_cursor={cursor}"
            data = await self.notion._request("GET", path)
            children.extend(data.get("results", []))
            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")
            if not cursor:
                break
        return children

    async def _table_rows(self, table_block_id: str, page_name: str) -> list[dict[str, str]]:
        rows = []
        blocks = await self._block_children(table_block_id)
        headers: list[str] = []
        for index, block in enumerate(blocks):
            if block.get("type") != "table_row":
                continue
            cells = (block.get("table_row") or {}).get("cells") or []
            values = ["".join(part.get("plain_text", "") for part in cell).strip() for cell in cells]
            if index == 0:
                headers = values
                continue
            row = {headers[i] if i < len(headers) and headers[i] else f"컬럼{i + 1}": value for i, value in enumerate(values)}
            row["_page_name"] = page_name
            row["_row_id"] = f"{table_block_id}:{index}"
            if looks_like_test_case_row(row):
                rows.append(row)
        return rows

    def _page_stats(self, page_name: str, rows: list[dict[str, str]]) -> TestCasePageStats:
        platform_counts: dict[str, TestCaseStatusCounts] = defaultdict(TestCaseStatusCounts)
        page_counts = TestCaseStatusCounts()
        for row in rows:
            for platform, raw_result in platform_results(row, page_name):
                status = normalize_tc_result(raw_result)
                add_status(platform_counts[platform], status)
                add_status(page_counts, status)
        return TestCasePageStats(
            page_name=page_name,
            **finalize_counts(page_counts).model_dump(),
            platforms=[
                TestCasePlatformStats(platform=platform, **finalize_counts(counts).model_dump())
                for platform, counts in sorted(platform_counts.items(), key=lambda item: platform_sort_key(item[0]))
            ],
        )


def parse_notion_id(value: str) -> str:
    ids = parse_notion_ids(value)
    if not ids:
        raise ValueError("Notion 링크에서 페이지 ID를 찾지 못했습니다.")
    return ids[0]


def parse_notion_ids(value: str) -> list[str]:
    ids = extract_notion_ids(value)
    if not ids:
        raise ValueError("Notion 링크에서 페이지 ID를 찾지 못했습니다.")
    return ids


def extract_notion_ids(value: str) -> list[str]:
    ids = []
    for match in re.finditer(r"([0-9a-fA-F]{32})", value or ""):
        ids.append(normalize_notion_id(match.group(1)))
    for match in re.finditer(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", value or ""):
        ids.append(normalize_notion_id(match.group(1)))
    return list(dict.fromkeys(ids))


def normalize_notion_id(value: str) -> str:
    clean = re.sub(r"[^0-9a-fA-F]", "", value or "")
    if len(clean) == 32:
        return f"{clean[:8]}-{clean[8:12]}-{clean[12:16]}-{clean[16:20]}-{clean[20:]}".lower()
    return value


def linked_notion_ids_from_block(block: dict[str, Any]) -> list[str]:
    block_id = normalize_notion_id(block.get("id", ""))
    ids: list[str] = []

    def add(value: str) -> None:
        normalized = normalize_notion_id(value)
        if normalized and normalized != block_id:
            ids.append(normalized)

    def walk(value: Any, parent_key: str = "", key: str = "") -> None:
        if isinstance(value, dict):
            for child_key, child_value in value.items():
                walk(child_value, key, child_key)
            return
        if isinstance(value, list):
            for item in value:
                walk(item, parent_key, key)
            return
        if isinstance(value, str) and key in {"page_id", "database_id"}:
            add(value)
            return
        if isinstance(value, str) and key == "id" and parent_key in {"page", "database"}:
            add(value)
            return
        if isinstance(value, str) and ("notion." in value or "app.notion.com" in value or "/p/" in value):
            for notion_id in extract_notion_ids(value):
                add(notion_id)

    walk(block)
    return list(dict.fromkeys(ids))


def linked_page_name_from_block(block: dict[str, Any], fallback: str) -> str:
    text = plain_text_from_value(block.get(block.get("type", ""), {}))
    if text:
        return text[:80]
    urls = text_values_from_value(block.get(block.get("type", ""), {}))
    for url in urls:
        name = source_page_name(url)
        if name:
            return name[:80]
    return fallback


def plain_text_from_value(value: Any) -> str:
    texts = []

    def walk(current: Any) -> None:
        if isinstance(current, dict):
            plain_text = current.get("plain_text")
            if isinstance(plain_text, str) and plain_text.strip():
                texts.append(plain_text.strip())
            for child in current.values():
                walk(child)
        elif isinstance(current, list):
            for item in current:
                walk(item)

    walk(value)
    return " ".join(texts).strip()


def text_values_from_value(value: Any) -> list[str]:
    values: list[str] = []

    def walk(current: Any) -> None:
        if isinstance(current, dict):
            for child in current.values():
                walk(child)
        elif isinstance(current, list):
            for item in current:
                walk(item)
        elif isinstance(current, str):
            values.append(current)

    walk(value)
    return values


def row_identity(row: dict[str, str]) -> str:
    if row.get("_row_id"):
        return row["_row_id"]
    return "|".join(f"{key}={value}" for key, value in sorted(row.items()) if not key.startswith("_"))


def source_page_name(value: str) -> str:
    match = re.search(r"/p/([^/?#]+)", value or "")
    if not match:
        return ""
    slug = match.group(1)
    clean = re.sub(r"-?[0-9a-fA-F]{32}$", "", slug).strip("-")
    return clean.replace("-", " ").strip()


def safe_error(exc: Exception) -> str:
    text = str(exc)
    return text[:180]


def count_values(values) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[str(value)] = counts.get(str(value), 0) + 1
    return counts


def block_title(block: dict[str, Any]) -> str:
    block_type = block.get("type", "")
    data = block.get(block_type) or {}
    title = data.get("title")
    if isinstance(title, str):
        return title[:80]
    if isinstance(title, list):
        return "".join(part.get("plain_text", "") for part in title)[:80]
    return ""


def page_to_row(page: dict[str, Any]) -> dict[str, str]:
    return {name: property_to_text(prop) for name, prop in (page.get("properties") or {}).items()}


def page_name_from_page(page: dict[str, Any]) -> str:
    for prop in (page.get("properties") or {}).values():
        if prop.get("type") == "title":
            return property_to_text(prop)
    return ""


def property_to_text(prop: dict[str, Any] | None) -> str:
    if not prop:
        return ""
    prop_type = prop.get("type")
    value = prop.get(prop_type)
    if prop_type in {"title", "rich_text"}:
        return "".join(item.get("plain_text", "") for item in value or []).strip()
    if prop_type in {"select", "status"}:
        return (value or {}).get("name", "") if isinstance(value, dict) else ""
    if prop_type == "multi_select":
        return ", ".join(item.get("name", "") for item in value or [] if item.get("name"))
    if prop_type == "checkbox":
        return "true" if value else "false"
    if prop_type == "number":
        return "" if value is None else str(value)
    if prop_type == "date":
        return (value or {}).get("start", "") if isinstance(value, dict) else ""
    if prop_type == "formula":
        return formula_to_text(value if isinstance(value, dict) else {})
    if prop_type == "rollup":
        return rollup_to_text(value if isinstance(value, dict) else {})
    if prop_type == "unique_id":
        if not isinstance(value, dict):
            return ""
        prefix = value.get("prefix") or ""
        number = value.get("number")
        return f"{prefix}-{number}" if prefix and number is not None else ("" if number is None else str(number))
    return "" if value is None else str(value)


def looks_like_test_case_row(row: dict[str, str]) -> bool:
    keys = {compact(key) for key in row}
    if any(compact(candidate) in keys for candidate in TC_TITLE_CANDIDATES):
        return True
    detected = detected_platform_columns(row)
    return bool(detected) or bool(find_column(row, OS_COLUMN_CANDIDATES) and find_column(row, RESULT_COLUMN_CANDIDATES))


def platform_results(row: dict[str, str], page_name: str = "") -> list[tuple[str, str]]:
    platform_columns = detected_platform_columns(row)
    if platform_columns:
        return [(platform, row.get(column, "")) for platform, column in platform_columns.items()]

    os_column = find_column(row, OS_COLUMN_CANDIDATES)
    result_column = find_column(row, RESULT_COLUMN_CANDIDATES)
    if os_column and result_column:
        return [(canonical_platform(row.get(os_column, "")), row.get(result_column, ""))]
    if os_column:
        status = status_from_status_columns(row)
        if status:
            return [(canonical_platform(row.get(os_column, "")), status)]

    page_platform = infer_platform(page_name)
    if page_platform:
        if result_column:
            return [(page_platform, row.get(result_column, ""))]
        status = status_from_status_columns(row)
        if status:
            return [(page_platform, status)]
    return []


def detected_platform_columns(row: dict[str, str]) -> dict[str, str]:
    result = {}
    keys = list(row)
    for platform, aliases in PLATFORM_ALIASES.items():
        for alias in aliases:
            column = find_column(row, (alias,))
            if column:
                result[platform] = column
                break
        if platform not in result:
            for key in keys:
                key_compact = compact(key)
                if any(compact(alias) in key_compact for alias in aliases):
                    result[platform] = key
                    break
    return result


def find_column(row: dict[str, str], candidates: tuple[str, ...]) -> str:
    compact_map = {compact(key): key for key in row}
    for candidate in candidates:
        found = compact_map.get(compact(candidate))
        if found:
            return found
    return ""


def compact(value: str) -> str:
    return re.sub(r"[\s/_()\[\]-]+", "", str(value or "").strip().lower())


def canonical_platform(value: str) -> str:
    text = str(value or "").strip()
    text_compact = compact(text)
    for platform, aliases in PLATFORM_ALIASES.items():
        if any(text_compact == compact(alias) for alias in aliases):
            return platform
    return text or "미분류"


def infer_platform(value: str) -> str:
    text_compact = compact(value)
    for platform, aliases in PLATFORM_ALIASES.items():
        if any(compact(alias) in text_compact for alias in aliases):
            return platform
    return ""


def normalize_tc_result(value: str) -> str:
    text = str(value or "").strip()
    key = re.sub(r"[\s/_-]+", "", text).upper()
    clean = re.sub(r"[^A-Za-z가-힣]+", "", text).upper()
    if not key:
        return "not_started"
    if key in {"PASS", "PASSED", "OK", "SUCCESS", "성공", "통과", "정상"} or clean in {"PASS", "PASSED", "OK"}:
        return "pass"
    if key in {"FAIL", "FAILED", "NG", "ERROR", "실패", "오류", "불합격"} or clean in {"FAIL", "FAILED", "NG"}:
        return "fail"
    if key in {"NA", "N/A", "NONE", "NULL", "해당없음", "해당무", "제외", "미대상"} or clean in {"NA", "NAN"}:
        return "na"
    return "other"


def status_from_status_columns(row: dict[str, str]) -> str:
    for status in ("PASS", "FAIL", "NA"):
        column = find_column(row, (status, f"{status} 여부", f"{status} 결과"))
        if column and truthy_cell(row.get(column, "")):
            return status
    return ""


def truthy_cell(value: str) -> bool:
    key = re.sub(r"[\s/_-]+", "", str(value or "")).upper()
    return key in {"TRUE", "YES", "Y", "1", "CHECKED", "체크", "확인", "O", "✓", "✅"}


def formula_to_text(value: dict[str, Any]) -> str:
    formula_type = value.get("type")
    raw = value.get(formula_type)
    if formula_type == "date":
        return (raw or {}).get("start", "") if isinstance(raw, dict) else ""
    if raw is None:
        return ""
    return str(raw)


def rollup_to_text(value: dict[str, Any]) -> str:
    rollup_type = value.get("type")
    raw = value.get(rollup_type)
    if rollup_type == "array":
        return ", ".join(property_to_text(item) for item in raw or [])
    if raw is None:
        return ""
    return str(raw)


def add_status(counts: TestCaseStatusCounts, status: str) -> None:
    counts.total_count += 1
    if status == "pass":
        counts.pass_count += 1
    elif status == "fail":
        counts.fail_count += 1
    elif status == "na":
        counts.na_count += 1
    elif status == "not_started":
        counts.not_started_count += 1
    else:
        counts.other_count += 1


def add_counts(target: TestCaseStatusCounts, source: TestCaseStatusCounts) -> None:
    target.total_count += source.total_count
    target.pass_count += source.pass_count
    target.fail_count += source.fail_count
    target.na_count += source.na_count
    target.not_started_count += source.not_started_count
    target.other_count += source.other_count


def finalize_counts(counts: TestCaseStatusCounts) -> TestCaseStatusCounts:
    completed = counts.pass_count + counts.fail_count + counts.na_count
    counts.progress_rate = round((completed / counts.total_count * 100), 1) if counts.total_count else 0.0
    return counts


def platform_sort_key(platform: str) -> tuple[int, str]:
    order = {"AOS": 0, "iOS": 1, "BO": 2, "Web": 3}
    return (order.get(platform, 99), platform.lower())
