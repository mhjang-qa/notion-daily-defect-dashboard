from __future__ import annotations

from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app.test_case_repository import normalize_tc_result, platform_results


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
