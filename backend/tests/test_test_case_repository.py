from __future__ import annotations

import asyncio
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app.test_case_repository import TestCaseRepository as TcRepository, linked_notion_ids_from_block, normalize_tc_result, platform_results


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


def test_platform_results_detects_os_and_status_columns():
    row = {
        "Test Case": "로그인",
        "OS": "iOS",
        "PASS": "true",
        "FAIL": "",
        "NA": "",
    }

    assert platform_results(row) == [("iOS", "PASS")]


def test_platform_results_uses_platform_page_name_with_result_column():
    row = {
        "Test Case": "로그인",
        "Result": "FAIL",
    }

    assert platform_results(row, "AOS 테스트케이스") == [("AOS", "FAIL")]


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


class FakeNestedSourceNotion:
    settings = SimpleNamespace(tz=ZoneInfo("Asia/Seoul"))

    async def _request(self, method: str, path: str, **kwargs):
        if method == "POST" and path == "/databases/00000000-0000-0000-0000-000000000001/query":
            return {"results": [], "has_more": False}
        if method == "GET" and path.startswith("/blocks/00000000-0000-0000-0000-000000000001/children"):
            return {"results": [], "has_more": False}
        if method == "POST" and path == "/databases/00000000-0000-0000-0000-000000000002/query":
            return {
                "results": [
                    {
                        "id": "os-row-1",
                        "properties": {
                            "Test Case": title_prop("TC-001"),
                            "Result": select_prop("PASS"),
                        },
                    }
                ],
                "has_more": False,
            }
        raise RuntimeError(path)


class FakeRootLinkTreeNotion:
    settings = SimpleNamespace(tz=ZoneInfo("Asia/Seoul"))

    root_id = "11111111-1111-1111-1111-111111111111"
    detail_id = "22222222-2222-2222-2222-222222222222"
    os_id = "33333333-3333-3333-3333-333333333333"

    async def _request(self, method: str, path: str, **kwargs):
        if method == "POST" and path == f"/databases/{self.os_id}/query":
            return {
                "results": [
                    {
                        "id": "tc-row-1",
                        "properties": {
                            "Test Case": title_prop("System_001_스플래쉬"),
                            "Result": select_prop("PASS"),
                        },
                    }
                ],
                "has_more": False,
            }
        if method == "POST" and path.endswith("/query"):
            return {"results": [], "has_more": False}
        if method == "GET" and path.startswith(f"/blocks/{self.root_id}/children"):
            return {
                "results": [
                    {
                        "id": "root-block-1",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [
                                {
                                    "plain_text": "BO 상세",
                                    "mention": {"type": "page", "page": {"id": self.detail_id}},
                                }
                            ]
                        },
                    }
                ],
                "has_more": False,
            }
        if method == "GET" and path.startswith(f"/blocks/{self.detail_id}/children"):
            compact_os_id = self.os_id.replace("-", "")
            return {
                "results": [
                    {
                        "id": "detail-block-1",
                        "type": "bookmark",
                        "bookmark": {
                            "url": f"https://app.notion.com/p/AOS-{compact_os_id}?source=copy_link",
                            "caption": [{"plain_text": "AOS 테스트케이스"}],
                        },
                    }
                ],
                "has_more": False,
            }
        if method == "GET" and path.startswith(f"/blocks/{self.os_id}/children"):
            return {"results": [], "has_more": False}
        raise RuntimeError(path)


def test_dashboard_keeps_database_rows_when_block_children_lookup_fails():
    repo = TcRepository(FakeDatabaseNotion())

    result = asyncio.run(repo.dashboard("https://app.notion.com/p/3a773fbd195180af93ddc50099a7df6c"))

    assert result.summary.total_count == 2
    assert result.summary.pass_count == 1
    assert result.summary.not_started_count == 1


def test_dashboard_collects_from_explicit_nested_source_urls():
    repo = TcRepository(FakeNestedSourceNotion())

    result = asyncio.run(
        repo.dashboard(
            "https://app.notion.com/p/root-id",
            source_urls=(
                "https://app.notion.com/p/00000000000000000000000000000001",
                "https://app.notion.com/p/AOS-00000000000000000000000000000002",
            ),
        )
    )

    assert result.summary.total_count == 1
    assert result.summary.pass_count == 1
    assert result.platforms[0].platform == "AOS"


def test_linked_notion_ids_from_block_detects_mentions_and_urls():
    block = {
        "id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [
                {"plain_text": "상세", "mention": {"type": "page", "page": {"id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"}}},
                {"href": "https://app.notion.com/p/CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC?source=copy_link"},
            ]
        },
    }

    assert linked_notion_ids_from_block(block) == [
        "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        "cccccccc-cccc-cccc-cccc-cccccccccccc",
    ]


def test_dashboard_traverses_root_page_links_to_os_test_case_pages():
    repo = TcRepository(FakeRootLinkTreeNotion())

    result = asyncio.run(
        repo.dashboard(
            f"https://app.notion.com/p/{FakeRootLinkTreeNotion.root_id.replace('-', '')}",
            source_urls=(f"https://app.notion.com/p/{FakeRootLinkTreeNotion.root_id.replace('-', '')}",),
        )
    )

    assert result.summary.total_count == 1
    assert result.summary.pass_count == 1
    assert result.pages[0].page_name == "AOS 테스트케이스"
    assert result.platforms[0].platform == "AOS"
