from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy import Select, delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from .models import DefectSnapshot, DefectSnapshotItem
from .schemas import CollectResponse, DefectRecord, SnapshotRow


class SnapshotService:
    def __init__(self, session: Session):
        self.session = session

    def collect(self, records: list[DefectRecord], snapshot_date: date, collected_at: datetime) -> CollectResponse:
        grouped: dict[str, list[DefectRecord]] = defaultdict(list)
        for record in records:
            grouped[record.target_version or "(목표버전 없음)"].append(record)

        created = 0
        updated = 0
        item_count = 0
        for target_version, version_records in grouped.items():
            snapshot, was_created = self._get_or_create_snapshot(snapshot_date, target_version, collected_at)
            if was_created:
                created += 1
            else:
                self.session.execute(delete(DefectSnapshotItem).where(DefectSnapshotItem.snapshot_id == snapshot.id))
                updated += 1

            stats = self._build_stats(version_records, snapshot_date, target_version)
            for key, value in stats.items():
                setattr(snapshot, key, value)
            snapshot.collected_at = collected_at
            snapshot.items = [self._record_to_item(snapshot.id, record) for record in version_records]
            item_count += len(version_records)
            self.session.commit()

        return CollectResponse(
            snapshot_date=snapshot_date,
            target_versions=sorted(grouped),
            snapshots_created=created,
            snapshots_updated=updated,
            item_count=item_count,
        )

    def ensure_today_snapshot(self, records_provider, today: date, now: datetime) -> CollectResponse | None:
        existing_count = self.session.scalar(select(func.count()).select_from(DefectSnapshot).where(DefectSnapshot.snapshot_date == today))
        if existing_count:
            return None
        records = records_provider()
        return self.collect(records, today, now)

    def target_versions(self) -> list[str]:
        rows = self.session.scalars(select(DefectSnapshot.target_version).distinct().order_by(DefectSnapshot.target_version)).all()
        return list(rows)

    def snapshot_count_for_date(self, snapshot_date: date) -> int:
        return int(
            self.session.scalar(
                select(func.count()).select_from(DefectSnapshot).where(DefectSnapshot.snapshot_date == snapshot_date)
            )
            or 0
        )

    def dashboard_rows(self, target_version: str, days: int | None = 30) -> list[SnapshotRow]:
        stmt: Select[tuple[DefectSnapshot]] = (
            select(DefectSnapshot)
            .where(DefectSnapshot.target_version == target_version)
            .order_by(DefectSnapshot.snapshot_date.asc())
        )
        if days:
            since = date.today() - timedelta(days=days - 1)
            stmt = stmt.where(DefectSnapshot.snapshot_date >= since)
        snapshots = list(self.session.scalars(stmt).all())
        rows: list[SnapshotRow] = []
        previous: DefectSnapshot | None = None
        for snapshot in snapshots:
            row = SnapshotRow.model_validate(snapshot)
            if previous:
                row.delta_total = snapshot.total_count - previous.total_count
                row.delta_unresolved = snapshot.unresolved_count - previous.unresolved_count
                row.delta_resolved = snapshot.resolved_count - previous.resolved_count
            rows.append(row)
            previous = snapshot
        return rows

    def latest_snapshot(self, target_version: str) -> DefectSnapshot | None:
        return self.session.scalar(
            select(DefectSnapshot)
            .where(DefectSnapshot.target_version == target_version)
            .order_by(DefectSnapshot.snapshot_date.desc())
            .limit(1)
        )

    def snapshot_items(self, snapshot_id: int) -> list[DefectSnapshotItem]:
        snapshot = self.session.scalar(
            select(DefectSnapshot)
            .options(selectinload(DefectSnapshot.items))
            .where(DefectSnapshot.id == snapshot_id)
        )
        return snapshot.items if snapshot else []

    def _build_stats(self, records: list[DefectRecord], snapshot_date: date, target_version: str) -> dict[str, int | float]:
        current_ids = {record.notion_page_id for record in records}
        seen_before = set(
            self.session.scalars(
                select(DefectSnapshotItem.notion_page_id)
                .join(DefectSnapshot)
                .where(
                    DefectSnapshot.target_version == target_version,
                    DefectSnapshot.snapshot_date < snapshot_date,
                )
            ).all()
        )
        previous_resolved = set(
            self.session.scalars(
                select(DefectSnapshotItem.notion_page_id)
                .join(DefectSnapshot)
                .where(
                    DefectSnapshot.target_version == target_version,
                    DefectSnapshot.snapshot_date < snapshot_date,
                    DefectSnapshotItem.status_group == "resolved",
                )
            ).all()
        )
        previous_latest = self.session.scalar(
            select(DefectSnapshot)
            .where(
                DefectSnapshot.target_version == target_version,
                DefectSnapshot.snapshot_date < snapshot_date,
            )
            .order_by(DefectSnapshot.snapshot_date.desc())
            .limit(1)
        )
        previous_latest_resolved_ids: set[str] = set()
        if previous_latest:
            previous_latest_resolved_ids = set(
                self.session.scalars(
                    select(DefectSnapshotItem.notion_page_id).where(
                        DefectSnapshotItem.snapshot_id == previous_latest.id,
                        DefectSnapshotItem.status_group == "resolved",
                    )
                ).all()
            )

        resolved_ids = {record.notion_page_id for record in records if record.status_group == "resolved"}
        in_progress = sum(1 for record in records if record.status_group == "in_progress")
        qa_verified = sum(1 for record in records if record.status_group == "qa_verified")
        resolved = len(resolved_ids)
        unresolved = len(records) - resolved - in_progress - qa_verified
        new_count = len(current_ids - seen_before)
        completed_today = len(resolved_ids - previous_latest_resolved_ids)
        reopened = sum(1 for record in records if record.notion_page_id in previous_resolved and record.status_group != "resolved")
        total = len(records)
        return {
            "total_count": total,
            "new_count": new_count,
            "in_progress_count": in_progress,
            "qa_verified_count": qa_verified,
            "unresolved_count": unresolved,
            "resolved_count": resolved,
            "reopened_count": reopened,
            "completed_today_count": completed_today,
            "net_change_count": new_count - completed_today,
            "resolution_rate": round((resolved / total * 100), 1) if total else 0.0,
        }

    def _snapshot_for_date(self, snapshot_date: date, target_version: str) -> DefectSnapshot | None:
        return self.session.scalar(
            select(DefectSnapshot).where(
                DefectSnapshot.snapshot_date == snapshot_date,
                DefectSnapshot.target_version == target_version,
            )
        )

    def _get_or_create_snapshot(self, snapshot_date: date, target_version: str, collected_at: datetime) -> tuple[DefectSnapshot, bool]:
        existing = self._snapshot_for_date(snapshot_date, target_version)
        if existing:
            return existing, False

        snapshot = DefectSnapshot(snapshot_date=snapshot_date, target_version=target_version, collected_at=collected_at)
        self.session.add(snapshot)
        try:
            self.session.flush()
            return snapshot, True
        except IntegrityError:
            self.session.rollback()
            existing = self._snapshot_for_date(snapshot_date, target_version)
            if not existing:
                raise
            return existing, False

    def _record_to_item(self, snapshot_id: int, record: DefectRecord) -> DefectSnapshotItem:
        return DefectSnapshotItem(
            snapshot_id=snapshot_id,
            notion_page_id=record.notion_page_id,
            title=record.title,
            status=record.status,
            status_group=record.status_group,
            severity=record.severity,
            priority=record.priority,
            target_version=record.target_version,
            notion_created_at=record.notion_created_at,
            notion_last_edited_at=record.notion_last_edited_at,
            url=record.url,
        )
