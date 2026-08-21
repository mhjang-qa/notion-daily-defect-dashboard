from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.schemas import DefectRecord
from app.snapshot_service import SnapshotService


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def record(page_id: str, status_group: str, target_version: str = "5.25.0") -> DefectRecord:
    return DefectRecord(
        notion_page_id=page_id,
        title=f"Defect {page_id}",
        status=status_group,
        status_group=status_group,
        target_version=target_version,
    )


def test_new_count_is_first_seen_not_total_delta():
    session = make_session()
    service = SnapshotService(session)
    now = datetime(2026, 8, 20, 8, 30, tzinfo=ZoneInfo("Asia/Seoul"))

    service.collect([record("a", "unresolved"), record("b", "resolved")], date(2026, 8, 20), now)
    service.collect(
        [record("a", "resolved"), record("b", "resolved"), record("c", "unresolved")],
        date(2026, 8, 21),
        now,
    )

    rows = service.dashboard_rows("5.25.0", None)
    assert rows[0].new_count == 2
    assert rows[1].new_count == 1
    assert rows[1].total_count == 3
    assert rows[1].completed_today_count == 1
    assert rows[1].net_change_count == 0


def test_reopened_count_detects_previous_resolved_item():
    session = make_session()
    service = SnapshotService(session)
    now = datetime(2026, 8, 20, 8, 30, tzinfo=ZoneInfo("Asia/Seoul"))

    service.collect([record("a", "resolved")], date(2026, 8, 20), now)
    service.collect([record("a", "unresolved")], date(2026, 8, 21), now)

    rows = service.dashboard_rows("5.25.0", None)
    assert rows[1].reopened_count == 1
    assert rows[1].unresolved_count == 1


def test_same_date_snapshot_updates_without_duplicate():
    session = make_session()
    service = SnapshotService(session)
    now = datetime(2026, 8, 20, 8, 30, tzinfo=ZoneInfo("Asia/Seoul"))

    first = service.collect([record("a", "unresolved")], date(2026, 8, 20), now)
    second = service.collect([record("a", "resolved"), record("b", "unresolved")], date(2026, 8, 20), now)

    rows = service.dashboard_rows("5.25.0", None)
    assert first.snapshots_created == 1
    assert second.snapshots_updated == 1
    assert len(rows) == 1
    assert rows[0].total_count == 2


def test_qa_verified_count_is_separate_from_progress_and_resolved():
    session = make_session()
    service = SnapshotService(session)
    now = datetime(2026, 8, 20, 8, 30, tzinfo=ZoneInfo("Asia/Seoul"))

    service.collect(
        [
            record("a", "qa_verified"),
            record("b", "in_progress"),
            record("c", "resolved"),
            record("d", "unresolved"),
        ],
        date(2026, 8, 20),
        now,
    )

    row = service.dashboard_rows("5.25.0", None)[0]
    assert row.qa_verified_count == 1
    assert row.in_progress_count == 1
    assert row.resolved_count == 1
    assert row.unresolved_count == 1
