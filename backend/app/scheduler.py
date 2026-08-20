from __future__ import annotations

import asyncio
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import Settings
from .database import SessionLocal
from .notion_repository import NotionRepository
from .snapshot_service import SnapshotService


async def collect_async(settings: Settings):
    repo = NotionRepository(settings)
    records = await repo.list_defects()
    now = datetime.now(settings.tz)
    with SessionLocal() as session:
        return SnapshotService(session).collect(records, now.date(), now)


def run_collection(settings: Settings):
    return asyncio.run(collect_async(settings))


def build_scheduler(settings: Settings) -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=settings.tz)
    scheduler.add_job(
        lambda: run_collection(settings),
        CronTrigger(hour=settings.scheduler_hour, minute=settings.scheduler_minute, timezone=settings.tz),
        id="daily_defect_snapshot",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    return scheduler
