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


def test_done_statuses_are_resolved():
    repo = NotionRepository(get_settings())

    for status in (
        "Known-Issue",
        "추적 관찰-백로그",
        "결함 아님 (Not an issue)",
        "추후 수정 백로그 이관",
        "완료 (Done)",
    ):
        assert repo._status_group(status_prop(status, "Complete")) == "resolved"


def test_in_progress_statuses_are_in_progress():
    repo = NotionRepository(get_settings())

    for status in (
        "기획서 수정",
        "처리중 (In Progress)",
        "개발 완료 (Dev Done)",
        "결함 재발생 (Reopen)",
    ):
        assert repo._status_group(status_prop(status, "In progress")) == "in_progress"


def test_qa_verification_status_is_qa_verified():
    repo = NotionRepository(get_settings())

    assert repo._status_group(status_prop("QA 검증 -회귀 (QA Verification)", "In progress")) == "qa_verified"


def test_todo_statuses_are_unresolved():
    repo = NotionRepository(get_settings())

    for status in ("등록 (Registered)", "배정 (Assigned)", "완료", "개발 완료"):
        assert repo._status_group(status_prop(status)) == "unresolved"
