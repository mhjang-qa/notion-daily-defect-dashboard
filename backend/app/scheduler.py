from __future__ import annotations

import asyncio
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import Settings
from .database import SessionLocal
from .embed_renderer import generate_hanpass_renewal_embed
from .github_pages import publish_embed_html_to_github_pages
from .notion_repository import NotionRepository
from .snapshot_service import SnapshotService
from .test_case_repository import DEFAULT_TEST_CASE_SOURCE_URL, TestCaseRepository


async def collect_async(settings: Settings):
    repo = NotionRepository(settings)
    records = await repo.list_defects()
    now = datetime.now(settings.tz)
    with SessionLocal() as session:
        return SnapshotService(session).collect(records, now.date(), now)


async def collect_and_publish_embed_async(settings: Settings):
    result = await collect_async(settings)
    test_cases = await TestCaseRepository(NotionRepository(settings)).dashboard(DEFAULT_TEST_CASE_SOURCE_URL)
    with SessionLocal() as session:
        generated_path = generate_hanpass_renewal_embed(session, test_cases=test_cases.model_dump(mode="json"))
    if settings.github_pages_token:
        await publish_embed_html_to_github_pages(settings, generated_path)
    return result


def run_collection(settings: Settings):
    return asyncio.run(collect_async(settings))


def run_collection_and_publish_embed(settings: Settings):
    return asyncio.run(collect_and_publish_embed_async(settings))


def build_scheduler(settings: Settings) -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=settings.tz)
    scheduler.add_job(
        lambda: run_collection_and_publish_embed(settings),
        CronTrigger(hour=settings.scheduler_hour, minute=settings.scheduler_minute, timezone=settings.tz),
        id="daily_defect_snapshot",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    return scheduler
