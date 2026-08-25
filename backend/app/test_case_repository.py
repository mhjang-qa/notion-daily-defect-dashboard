from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
from typing import Any

from .notion_repository import NotionRepository
from .schemas import TestCaseDashboardResponse, TestCasePageStats, TestCasePlatformStats, TestCaseStatusCounts


DEFAULT_TEST_CASE_SOURCE_URL = (
    "https://app.notion.com/p/3a773fbd195180af93ddc50099a7df6c"
    "?v=dae73fbd1951832d8e5908953dad8da6&source=copy_link"
)

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

    async def dashboard(self, source_url: str = DEFAULT_TEST_CASE_SOURCE_URL) -> TestCaseDashboardResponse:
        rows = []
        seen_row_keys = set()
        for source_id in parse_notion_ids(source_url):
            try:
                candidate_rows = await self._collect_rows(source_id, "테스트케이스")
            except Exception:
                continue
            for row in candidate_rows:
                key = row_identity(row)
                if key in seen_row_keys:
                    continue
                seen_row_keys.add(key)
                rows.append(row)
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

    async def _collect_rows(self, notion_id: str, page_name: str, depth: int = 4, visited: set[str] | None = None) -> list[dict[str, str]]:
        if depth <= 0:
            return []
        visited = visited or set()
        if notion_id in visited:
            return []
        visited.add(notion_id)

        rows = []
        try:
            pages = await self._query_database(notion_id)
            for page in pages:
                row = page_to_row(page)
                row["_page_name"] = page_name_from_page(page) or page_name
                row["_row_id"] = page.get("id", "")
                if looks_like_test_case_row(row):
                    rows.append(row)
                rows.extend(await self._collect_rows(page.get("id", ""), row["_page_name"], depth - 1, visited))
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
                for page in database_pages:
                    row = page_to_row(page)
                    row["_page_name"] = title
                    row["_row_id"] = page.get("id", "")
                    if looks_like_test_case_row(row):
                        rows.append(row)
                    rows.extend(await self._collect_rows(page.get("id", ""), title, depth - 1, visited))
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
            elif block.get("has_children"):
                rows.extend(await self._collect_rows(block_id, page_name, depth - 1, visited))
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
            for platform, raw_result in platform_results(row):
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
    ids = []
    for match in re.finditer(r"([0-9a-fA-F]{32})", value or ""):
        clean = re.sub(r"[^0-9a-fA-F]", "", match.group(1))
        ids.append(f"{clean[:8]}-{clean[8:12]}-{clean[12:16]}-{clean[16:20]}-{clean[20:]}")
    for match in re.finditer(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", value or ""):
        clean = re.sub(r"[^0-9a-fA-F]", "", match.group(1))
        ids.append(f"{clean[:8]}-{clean[8:12]}-{clean[12:16]}-{clean[16:20]}-{clean[20:]}")
    deduped = list(dict.fromkeys(ids))
    if not deduped:
        raise ValueError("Notion 링크에서 페이지 ID를 찾지 못했습니다.")
    return deduped


def row_identity(row: dict[str, str]) -> str:
    if row.get("_row_id"):
        return row["_row_id"]
    return "|".join(f"{key}={value}" for key, value in sorted(row.items()) if not key.startswith("_"))


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
    return "" if value is None else str(value)


def looks_like_test_case_row(row: dict[str, str]) -> bool:
    keys = {compact(key) for key in row}
    if any(compact(candidate) in keys for candidate in TC_TITLE_CANDIDATES):
        return True
    detected = detected_platform_columns(row)
    return bool(detected) or bool(find_column(row, OS_COLUMN_CANDIDATES) and find_column(row, RESULT_COLUMN_CANDIDATES))


def platform_results(row: dict[str, str]) -> list[tuple[str, str]]:
    platform_columns = detected_platform_columns(row)
    if platform_columns:
        return [(platform, row.get(column, "")) for platform, column in platform_columns.items()]

    os_column = find_column(row, OS_COLUMN_CANDIDATES)
    result_column = find_column(row, RESULT_COLUMN_CANDIDATES)
    if os_column and result_column:
        return [(canonical_platform(row.get(os_column, "")), row.get(result_column, ""))]
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
