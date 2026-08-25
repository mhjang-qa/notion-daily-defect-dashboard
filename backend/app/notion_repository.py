from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import httpx

from .config import Settings
from .schemas import DefectRecord
from .target_versions import normalize_target_versions, sort_target_versions


class NotionConfigurationError(RuntimeError):
    pass


class PropertyMapping:
    def __init__(self, properties: dict[str, Any]):
        self.properties = properties
        self.title = self._find_by_type("title")
        self.status = self._find_by_names(("상태", "Status", "status"), fallback_type="status")
        self.target_version = self._find_by_names(
            ("목표버전", "목표 버전", "Target Version", "target_version", "Version", "버전"),
        )
        self.severity = self._find_by_names(("Severity", "severity", "심각도"), required=False)
        self.priority = self._find_by_names(("Priority", "priority", "우선순위"), required=False)

        missing = []
        if not self.title:
            missing.append("title")
        if not self.status:
            missing.append("status")
        if not self.target_version:
            missing.append("target_version")
        if missing:
            raise NotionConfigurationError(f"Missing required Notion properties: {', '.join(missing)}")

    def _find_by_type(self, property_type: str) -> str:
        for name, prop in self.properties.items():
            if prop.get("type") == property_type:
                return name
        return ""

    def _find_by_names(
        self,
        names: tuple[str, ...],
        *,
        fallback_type: str | None = None,
        required: bool = True,
    ) -> str:
        lowered = {name.lower(): name for name in self.properties}
        for candidate in names:
            found = lowered.get(candidate.lower())
            if found:
                return found
        if fallback_type:
            by_type = self._find_by_type(fallback_type)
            if by_type:
                return by_type
        return "" if not required else ""


class NotionRepository:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = "https://api.notion.com/v1"
        self.headers = {
            "Authorization": f"Bearer {settings.notion_token}",
            "Notion-Version": settings.notion_version,
            "Content-Type": "application/json",
        }

    def _require_config(self) -> None:
        if not self.settings.notion_token:
            raise NotionConfigurationError("NOTION_TOKEN is not configured.")
        if not self.settings.notion_database_id:
            raise NotionConfigurationError("NOTION_DATABASE_ID is not configured.")

    async def get_property_mapping(self) -> PropertyMapping:
        self._require_config()
        data = await self._request("GET", f"/databases/{self.settings.notion_database_id}")
        return PropertyMapping(data.get("properties", {}))

    async def list_defects(self) -> list[DefectRecord]:
        mapping = await self.get_property_mapping()
        pages = await self._query_all_pages()
        return [self._page_to_record(page, mapping) for page in pages]

    async def list_target_versions(self) -> list[str]:
        records = await self.list_defects()
        versions = {
            version
            for record in records
            for version in normalize_target_versions(record.target_version)
            if version
        }
        return sort_target_versions(list(versions))

    async def _query_all_pages(self) -> list[dict[str, Any]]:
        pages: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            payload: dict[str, Any] = {"page_size": 100}
            if cursor:
                payload["start_cursor"] = cursor
            data = await self._request("POST", f"/databases/{self.settings.notion_database_id}/query", json=payload)
            pages.extend(data.get("results", []))
            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")
            if not cursor:
                break
        return pages

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        timeout = httpx.Timeout(30.0, connect=10.0)
        last_error: Exception | None = None
        async with httpx.AsyncClient(headers=self.headers, timeout=timeout) as client:
            for attempt in range(5):
                try:
                    response = await client.request(method, url, **kwargs)
                    if response.status_code in {429, 500, 502, 503, 504}:
                        retry_after = response.headers.get("Retry-After")
                        delay = float(retry_after) if retry_after else min(2**attempt, 16)
                        await asyncio.sleep(delay)
                        continue
                    response.raise_for_status()
                    return response.json()
                except (httpx.HTTPError, ValueError) as exc:
                    last_error = exc
                    await asyncio.sleep(min(2**attempt, 16))
        raise RuntimeError(f"Notion API request failed after retries: {last_error}")

    def _page_to_record(self, page: dict[str, Any], mapping: PropertyMapping) -> DefectRecord:
        properties = page.get("properties", {})
        target_version = self._property_to_text(properties.get(mapping.target_version))
        return DefectRecord(
            notion_page_id=page.get("id", ""),
            title=self._property_to_text(properties.get(mapping.title)),
            status=self._property_to_text(properties.get(mapping.status)),
            status_group=self._status_group(properties.get(mapping.status)),
            severity=self._property_to_text(properties.get(mapping.severity)) if mapping.severity else "",
            priority=self._property_to_text(properties.get(mapping.priority)) if mapping.priority else "",
            target_version=target_version or "(목표버전 없음)",
            notion_created_at=self._parse_datetime(page.get("created_time")),
            notion_last_edited_at=self._parse_datetime(page.get("last_edited_time")),
            url=page.get("url", ""),
        )

    def _status_group(self, prop: dict[str, Any] | None) -> str:
        if not prop:
            return "unresolved"
        text = self._property_to_text(prop).lower()
        resolved_statuses = {
            "known-issue",
            "추적 관찰-백로그",
            "결함 아님 (not an issue)",
            "추후 수정 백로그 이관",
            "완료 (done)",
        }
        if text in resolved_statuses:
            return "resolved"
        in_progress_statuses = {
            "기획서 수정",
            "처리중 (in progress)",
            "개발 완료 (dev done)",
            "결함 재발생 (reopen)",
        }
        if text == "qa 검증 -회귀 (qa verification)":
            return "qa_verified"
        if text in in_progress_statuses:
            return "in_progress"
        if prop.get("type") == "status":
            status = prop.get("status") or {}
            group = (status.get("group") or {}).get("name", "").lower()
            if "progress" in group:
                return "in_progress"
        progress_keywords = ("progress", "doing", "처리중", "진행", "개발중", "수정중")
        if any(keyword in text for keyword in progress_keywords):
            return "in_progress"
        return "unresolved"

    def _property_to_text(self, prop: dict[str, Any] | None) -> str:
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
        if prop_type == "date":
            return (value or {}).get("start", "") if isinstance(value, dict) else ""
        if prop_type == "people":
            return ", ".join(item.get("name", "") for item in value or [] if item.get("name"))
        if prop_type == "checkbox":
            return "true" if value else "false"
        if value is None:
            return ""
        return str(value)

    def _parse_datetime(self, value: str | None) -> datetime | None:
        if not value:
            return None
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
