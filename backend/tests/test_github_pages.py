from app.github_pages import extract_snapshot_payload, merge_embed_html_snapshots
from app.embed_renderer import generate_hanpass_renewal_embed, render_hanpass_renewal_embed


NATIVE_VERSION = "[Hanpass][앱개편][Native]"
BO_VERSION = "[Hanpass][앱개편][BO]"
PLANNING_VERSION = "[Hanpass][앱개편][기획]"


def row(snapshot_date: str, total_count: int) -> dict:
    return {
        "id": total_count,
        "snapshot_date": snapshot_date,
        "target_version": NATIVE_VERSION,
        "total_count": total_count,
        "new_count": total_count,
        "in_progress_count": 0,
        "qa_verified_count": 0,
        "unresolved_count": total_count,
        "resolved_count": 0,
        "reopened_count": 0,
        "completed_today_count": 0,
        "net_change_count": total_count,
        "resolution_rate": 0.0,
        "collected_at": "2026-08-21T10:00:00+09:00",
    }


def test_merge_embed_html_snapshots_keeps_fresh_detail_items():
    existing_html = render_hanpass_renewal_embed(
        [
            {
                "version": "[Hanpass][앱개편]",
                "rows": [row("2026-08-20", 25)],
                "items": [],
            }
        ],
        "2026-08-20T10:00:00+09:00",
    )
    fresh_html = render_hanpass_renewal_embed(
        [
            {
                "version": "[Hanpass][앱개편]",
                "rows": [row("2026-08-21", 31)],
                "items": [
                    {
                        "notion_page_id": "page-1",
                        "title": "로그인 오류",
                        "status": "처리중 (In Progress)",
                        "status_group": "in_progress",
                        "severity": "High",
                        "priority": "P1",
                        "target_version": NATIVE_VERSION,
                        "notion_created_at": None,
                        "notion_last_edited_at": None,
                        "url": "https://notion.so/page-1",
                    }
                ],
            }
        ],
        "2026-08-21T10:00:00+09:00",
    )

    merged = merge_embed_html_snapshots(existing_html, fresh_html)
    payload = extract_snapshot_payload(merged)

    assert payload is not None
    assert [item["title"] for item in payload["groups"][0]["items"]] == ["로그인 오류"]
    assert [row["snapshot_date"] for row in payload["groups"][0]["rows"]] == ["2026-08-20", "2026-08-21"]
    assert payload["groups"][0]["version"] == NATIVE_VERSION
    assert payload["groups"][0]["rows"][0]["target_version"] == NATIVE_VERSION
    assert payload["groups"][0]["items"][0]["target_version"] == NATIVE_VERSION


def test_merge_embed_html_snapshots_sorts_hanpass_renewal_versions():
    existing_html = render_hanpass_renewal_embed(
        [
            {"version": "[Hanpass][앱개편]", "rows": [row("2026-08-20", 25)], "items": []},
            {"version": BO_VERSION, "rows": [row("2026-08-20", 10)], "items": []},
        ],
        "2026-08-20T10:00:00+09:00",
    )
    fresh_html = render_hanpass_renewal_embed(
        [
            {"version": BO_VERSION, "rows": [row("2026-08-21", 11)], "items": []},
            {"version": PLANNING_VERSION, "rows": [row("2026-08-21", 3)], "items": []},
            {"version": NATIVE_VERSION, "rows": [row("2026-08-21", 31)], "items": []},
        ],
        "2026-08-21T10:00:00+09:00",
    )

    merged = merge_embed_html_snapshots(existing_html, fresh_html)
    payload = extract_snapshot_payload(merged)

    assert [group["version"] for group in payload["groups"]] == [NATIVE_VERSION, BO_VERSION, PLANNING_VERSION]
    assert "[Hanpass][앱개편], [Hanpass][앱개편][BO] 전용 Notion Embed" not in merged
    assert "[Hanpass][앱개편][Native], [Hanpass][앱개편][BO], [Hanpass][앱개편][기획]" in merged


def test_generate_embed_serializes_snapshot_items(monkeypatch, tmp_path):
    class Item:
        notion_page_id = "page-1"
        title = "로그인 오류"
        status = "처리중 (In Progress)"
        status_group = "in_progress"
        severity = "High"
        priority = "P1"
        target_version = NATIVE_VERSION
        notion_created_at = None
        notion_last_edited_at = None
        url = "https://notion.so/page-1"

    class Service:
        def __init__(self, session):
            pass

        def dashboard_rows(self, version, _days):
            return [type("Row", (), {"id": 1, "model_dump": lambda self, mode: row("2026-08-21", 1)})()]

        def snapshot_items(self, snapshot_id):
            return [Item()]

        def first_status_dates(self, version, notion_page_ids):
            return {"page-1": {"resolved": "2026-08-21"}}

    output = tmp_path / "embed.html"
    monkeypatch.setattr("app.embed_renderer.GENERATED_EMBED_PATH", output)
    monkeypatch.setattr("app.embed_renderer.SnapshotService", Service)

    generate_hanpass_renewal_embed(session=object())
    payload = extract_snapshot_payload(output.read_text(encoding="utf-8"))

    assert payload["groups"][0]["items"][0]["title"] == "로그인 오류"
    assert payload["groups"][0]["items"][0]["resolved_first_seen_date"] == "2026-08-21"


def test_hanpass_renewal_embed_renders_three_target_versions():
    html = render_hanpass_renewal_embed(
        [
            {"version": NATIVE_VERSION, "rows": [row("2026-08-24", 2)], "items": []},
            {"version": BO_VERSION, "rows": [row("2026-08-24", 1)], "items": []},
            {"version": PLANNING_VERSION, "rows": [row("2026-08-24", 3)], "items": []},
        ],
        "2026-08-24T17:33:00+09:00",
    )
    payload = extract_snapshot_payload(html)

    assert [group["version"] for group in payload["groups"]] == [NATIVE_VERSION, BO_VERSION, PLANNING_VERSION]
    assert "[Hanpass][앱개편][Native], [Hanpass][앱개편][BO], [Hanpass][앱개편][기획]" in html
    assert 'if (version === "[Hanpass][앱개편][기획]") return "기획";' in html


def test_hanpass_renewal_embed_embeds_test_case_snapshot_without_fetch():
    html = render_hanpass_renewal_embed(
        [{"version": NATIVE_VERSION, "rows": [row("2026-08-24", 2)], "items": []}],
        "2026-08-24T17:33:00+09:00",
        test_cases={
            "summary": {
                "total_count": 10,
                "pass_count": 7,
                "fail_count": 1,
                "na_count": 1,
                "not_started_count": 1,
                "other_count": 0,
                "progress_rate": 90.0,
            },
            "platforms": [],
            "pages": [],
        },
    )
    payload = extract_snapshot_payload(html)

    assert payload["testCases"]["summary"]["total_count"] == 10
    assert "/api/test-cases" not in html


def test_merge_embed_html_snapshots_uses_fresh_test_case_snapshot():
    existing_html = render_hanpass_renewal_embed(
        [{"version": NATIVE_VERSION, "rows": [row("2026-08-20", 2)], "items": []}],
        "2026-08-20T10:00:00+09:00",
        test_cases={"summary": {"total_count": 1}, "platforms": [], "pages": []},
    )
    fresh_html = render_hanpass_renewal_embed(
        [{"version": NATIVE_VERSION, "rows": [row("2026-08-21", 3)], "items": []}],
        "2026-08-21T10:00:00+09:00",
        test_cases={"summary": {"total_count": 20}, "platforms": [], "pages": []},
    )

    payload = extract_snapshot_payload(merge_embed_html_snapshots(existing_html, fresh_html))

    assert payload["testCases"]["summary"]["total_count"] == 20
