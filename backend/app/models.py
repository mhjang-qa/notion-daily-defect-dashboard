from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class DefectSnapshot(Base):
    __tablename__ = "defect_snapshot"
    __table_args__ = (UniqueConstraint("snapshot_date", "target_version", name="uq_snapshot_date_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_date: Mapped[date] = mapped_column(Date, index=True)
    target_version: Mapped[str] = mapped_column(String(255), index=True)
    total_count: Mapped[int] = mapped_column(Integer, default=0)
    new_count: Mapped[int] = mapped_column(Integer, default=0)
    in_progress_count: Mapped[int] = mapped_column(Integer, default=0)
    unresolved_count: Mapped[int] = mapped_column(Integer, default=0)
    resolved_count: Mapped[int] = mapped_column(Integer, default=0)
    reopened_count: Mapped[int] = mapped_column(Integer, default=0)
    completed_today_count: Mapped[int] = mapped_column(Integer, default=0)
    net_change_count: Mapped[int] = mapped_column(Integer, default=0)
    resolution_rate: Mapped[float] = mapped_column(Float, default=0.0)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    items: Mapped[list["DefectSnapshotItem"]] = relationship(
        back_populates="snapshot",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class DefectSnapshotItem(Base):
    __tablename__ = "defect_snapshot_items"
    __table_args__ = (UniqueConstraint("snapshot_id", "notion_page_id", name="uq_snapshot_item_page"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("defect_snapshot.id", ondelete="CASCADE"), index=True)
    notion_page_id: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(100), default="")
    status_group: Mapped[str] = mapped_column(String(30), default="unresolved", index=True)
    severity: Mapped[str] = mapped_column(String(100), default="")
    priority: Mapped[str] = mapped_column(String(100), default="")
    target_version: Mapped[str] = mapped_column(String(255), index=True)
    notion_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notion_last_edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    url: Mapped[str] = mapped_column(Text, default="")

    snapshot: Mapped[DefectSnapshot] = relationship(back_populates="items")
