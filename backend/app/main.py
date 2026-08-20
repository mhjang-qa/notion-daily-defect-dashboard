from __future__ import annotations

from threading import Thread
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from .config import get_settings
from .database import SessionLocal, get_session, init_db
from .notion_repository import NotionRepository
from .scheduler import build_scheduler, collect_async, run_collection
from .schemas import CollectResponse, DashboardResponse, SnapshotItemRow
from .snapshot_service import SnapshotService


settings = get_settings()
app = FastAPI(title="Notion Daily Defect Dashboard", version="0.1.0")
scheduler = None

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

frontend_dist = settings.frontend_dist_path
assets_dir = frontend_dist / "assets"
if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.on_event("startup")
def startup() -> None:
    global scheduler
    init_db()
    if settings.scheduler_enabled:
        scheduler = build_scheduler(settings)
        scheduler.start()
        Thread(target=_collect_missing_today_snapshot, daemon=True).start()


@app.on_event("shutdown")
def shutdown() -> None:
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "timezone": settings.timezone}


@app.get("/api/target-versions")
async def target_versions(session: Session = Depends(get_session)) -> dict[str, list[str]]:
    stored = SnapshotService(session).target_versions()
    if stored:
        return {"target_versions": stored}
    repo = NotionRepository(settings)
    try:
        versions = await repo.list_target_versions()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"target_versions": versions}


@app.post("/api/collect", response_model=CollectResponse)
async def collect_now() -> CollectResponse:
    try:
        return await collect_async(settings)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/dashboard", response_model=DashboardResponse)
def dashboard(
    target_version: str = Query(...),
    range: str = Query("30d"),
    session: Session = Depends(get_session),
) -> DashboardResponse:
    days = _range_to_days(range)
    service = SnapshotService(session)
    rows = service.dashboard_rows(target_version, days)
    updated_at = max((row.collected_at for row in rows), default=None)
    return DashboardResponse(target_version=target_version, updated_at=updated_at, rows=rows)


@app.get("/api/snapshots/{snapshot_id}/items", response_model=list[SnapshotItemRow])
def snapshot_items(snapshot_id: int, session: Session = Depends(get_session)) -> list[SnapshotItemRow]:
    items = SnapshotService(session).snapshot_items(snapshot_id)
    return [SnapshotItemRow.model_validate(item) for item in items]


def _range_to_days(value: str) -> int | None:
    if value == "all":
        return None
    if value.endswith("d") and value[:-1].isdigit():
        return int(value[:-1])
    return 30


@app.get("/", response_model=None)
def index():
    index_path = settings.frontend_dist_path / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"status": "ok", "message": "Frontend build not found. Run npm run build in frontend."}


@app.head("/", response_model=None)
def index_head():
    return Response(status_code=200)


@app.get("/{full_path:path}", response_model=None)
def spa_fallback(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not found")
    index_path = settings.frontend_dist_path / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="Frontend build not found")


def _collect_missing_today_snapshot() -> None:
    if not settings.notion_token or not settings.notion_database_id:
        return
    today = datetime.now(settings.tz).date()
    with SessionLocal() as session:
        if SnapshotService(session).snapshot_count_for_date(today):
            return
    try:
        run_collection(settings)
    except Exception:
        pass
