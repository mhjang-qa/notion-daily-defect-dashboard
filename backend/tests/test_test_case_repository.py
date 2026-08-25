from __future__ import annotations

import asyncio
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app.test_case_repository import TestCaseRepository as TcRepository, normalize_tc_result, platform_results


def test_normalize_tc_result_counts_blank_as_not_started():
    assert normalize_tc_result("") == "not_started"
    assert normalize_tc_result("PASS") == "pass"
    assert normalize_tc_result("FAIL") == "fail"
    assert normalize_tc_result("N/A") == "na"
    assert normalize_tc_result("확인 필요") == "other"


def test_platform_results_detects_os_result_columns():
    row = {
        "TC-ID": "TC-001",
        "AOS": "PASS",
        "iOS": "",
        "BO": "FAIL",
    }

    assert platform_results(row) == [
        ("AOS", "PASS"),
        ("iOS", ""),
        ("BO", "FAIL"),
    ]


def test_platform_results_detects_os_and_result_pair():
    row = {
        "Test Case": "로그인",
        "OS": "Android",
        "Result": "NA",
    }

    assert platform_results(row) == [("AOS", "NA")]


def test_fake_notion_settings_shape_for_repository_tests():
    settings = SimpleNamespace(tz=ZoneInfo("Asia/Seoul"))

    assert settings.tz.key == "Asia/Seoul"


def title_prop(value: str) -> dict:
    return {"type": "title", "title": [{"plain_text": value}]}


def select_prop(value: str) -> dict:
    return {"type": "select", "select": {"name": value}}


class FakeDatabaseNotion:
    settings = SimpleNamespace(tz=ZoneInfo("Asia/Seoul"))

    async def _request(self, method: str, path: str, **kwargs):
        if method == "POST" and path.endswith("/query"):
            return {
                "results": [
                    {
                        "id": "row-1",
                        "properties": {
                            "TC-ID": title_prop("TC-001"),
                            "AOS": select_prop("PASS"),
                            "iOS": select_prop(""),
                        },
                    }
                ],
                "has_more": False,
            }
        raise RuntimeError("block children are unavailable for database ids")


def test_dashboard_keeps_database_rows_when_block_children_lookup_fails():
    repo = TcRepository(FakeDatabaseNotion())

    result = asyncio.run(repo.dashboard("https://app.notion.com/p/3a773fbd195180af93ddc50099a7df6c"))

    assert result.summary.total_count == 2
    assert result.summary.pass_count == 1
    assert result.summary.not_started_count == 1
