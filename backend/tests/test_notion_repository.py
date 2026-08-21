from __future__ import annotations

from app.config import get_settings
from app.notion_repository import NotionRepository


def status_prop(name: str, group: str = "") -> dict:
    return {
        "type": "status",
        "status": {
            "name": name,
            "group": {"name": group},
        },
    }


def test_only_final_qa_statuses_are_resolved():
    repo = NotionRepository(get_settings())

    assert repo._status_group(status_prop("QA 검증 -회귀 (QA Verification)", "Complete")) == "resolved"
    assert repo._status_group(status_prop("완료 (Done)", "Complete")) == "resolved"
    assert repo._status_group(status_prop("QA 검증 -회귀", "Complete")) == "unresolved"
    assert repo._status_group(status_prop("완료", "Complete")) == "unresolved"


def test_progress_status_is_still_in_progress():
    repo = NotionRepository(get_settings())

    assert repo._status_group(status_prop("수정중", "In progress")) == "in_progress"
    assert repo._status_group(status_prop("개발 완료", "Complete")) == "in_progress"
