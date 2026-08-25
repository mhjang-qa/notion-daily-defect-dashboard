from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class DefectRecord(BaseModel):
    notion_page_id: str
    title: str = ""
    status: str = ""
    status_group: str = "unresolved"
    severity: str = ""
    priority: str = ""
    target_version: str = ""
    notion_created_at: datetime | None = None
    notion_last_edited_at: datetime | None = None
    url: str = ""


class SnapshotRow(BaseModel):
    id: int
    snapshot_date: date
    target_version: str
    total_count: int
    new_count: int
    in_progress_count: int
    qa_verified_count: int = 0
    unresolved_count: int
    resolved_count: int
    reopened_count: int
    completed_today_count: int
    net_change_count: int
    resolution_rate: float
    collected_at: datetime
    delta_total: int | None = None
    delta_unresolved: int | None = None
    delta_resolved: int | None = None

    model_config = {"from_attributes": True}


class SnapshotItemRow(BaseModel):
    notion_page_id: str
    title: str
    status: str
    status_group: str
    severity: str
    priority: str
    target_version: str
    notion_created_at: datetime | None
    notion_last_edited_at: datetime | None
    url: str

    model_config = {"from_attributes": True}


class DashboardResponse(BaseModel):
    target_version: str
    updated_at: datetime | None
    rows: list[SnapshotRow]


class CollectResponse(BaseModel):
    snapshot_date: date
    target_versions: list[str]
    snapshots_created: int
    snapshots_updated: int
    item_count: int


class TestCaseStatusCounts(BaseModel):
    total_count: int = 0
    pass_count: int = 0
    fail_count: int = 0
    na_count: int = 0
    not_started_count: int = 0
    other_count: int = 0
    progress_rate: float = 0.0


class TestCasePlatformStats(TestCaseStatusCounts):
    platform: str


class TestCasePageStats(TestCaseStatusCounts):
    page_name: str
    platforms: list[TestCasePlatformStats]


class TestCaseDashboardResponse(BaseModel):
    source_url: str
    updated_at: datetime
    summary: TestCaseStatusCounts
    platforms: list[TestCasePlatformStats]
    pages: list[TestCasePageStats]
