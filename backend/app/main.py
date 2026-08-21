from __future__ import annotations

import hashlib
import hmac
import time
from datetime import datetime
from threading import Thread

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .config import get_settings
from .database import SessionLocal, get_session, init_db
from .embed_renderer import GENERATED_EMBED_PATH, generate_hanpass_renewal_embed, render_admin_page
from .github_pages import publish_embed_html_to_github_pages
from .notion_repository import NotionRepository
from .scheduler import build_scheduler, collect_async, run_collection
from .schemas import CollectResponse, DashboardResponse, SnapshotItemRow
from .snapshot_service import SnapshotService


settings = get_settings()
app = FastAPI(title="Notion Daily Defect Dashboard", version="0.1.0")
scheduler = None
ADMIN_PASSWORD = "xptmxm123!"
ADMIN_COOKIE_NAME = "hanpass_embed_admin"
ADMIN_COOKIE_TTL_SECONDS = 12 * 60 * 60


class AdminLoginRequest(BaseModel):
    password: str

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
        result = await collect_async(settings)
        with SessionLocal() as session:
            generate_hanpass_renewal_embed(session)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/embed/hanpass-renewal/sync")
async def sync_hanpass_renewal_embed(request: Request) -> dict[str, str | bool]:
    require_embed_admin(request)
    try:
        await collect_async(settings)
        with SessionLocal() as session:
            generated_path = generate_hanpass_renewal_embed(session)
        publish_result = await publish_embed_html_to_github_pages(settings, generated_path)
        return {
            "ok": True,
            "generated_path": str(generated_path),
            "pages_url": settings.github_pages_url,
            "github_html_url": publish_result.html_url,
            "commit_sha": publish_result.commit_sha,
            "content_sha": publish_result.content_sha,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/embed/hanpass-renewal/admin-login")
def login_hanpass_renewal_embed_admin(payload: AdminLoginRequest, request: Request) -> JSONResponse:
    if not hmac.compare_digest(payload.password, ADMIN_PASSWORD):
        raise HTTPException(status_code=401, detail="Invalid password")
    response = JSONResponse({"ok": True})
    is_cross_origin = bool(request.headers.get("origin"))
    response.set_cookie(
        ADMIN_COOKIE_NAME,
        make_embed_admin_token(),
        max_age=ADMIN_COOKIE_TTL_SECONDS,
        httponly=True,
        secure=is_cross_origin or request.url.scheme == "https",
        samesite="none" if is_cross_origin else "lax",
        path="/",
    )
    return response


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


@app.get("/embed/hanpass-renewal", response_model=None)
@app.get("/embed/hanpass-renewal.html", response_model=None)
def hanpass_renewal_embed():
    if not GENERATED_EMBED_PATH.exists():
        with SessionLocal() as session:
            generate_hanpass_renewal_embed(session)
    if GENERATED_EMBED_PATH.exists():
        return FileResponse(GENERATED_EMBED_PATH)
    raise HTTPException(status_code=404, detail="Embed page not found")


@app.get("/embed/hanpass-renewal-admin", response_model=None)
def hanpass_renewal_embed_admin(request: Request):
    require_embed_admin(request)
    return HTMLResponse(render_admin_page())


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


def make_embed_admin_token() -> str:
    expires_at = str(int(time.time()) + ADMIN_COOKIE_TTL_SECONDS)
    signature = hmac.new(_embed_admin_secret(), expires_at.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{expires_at}:{signature}"


def require_embed_admin(request: Request) -> None:
    token = request.cookies.get(ADMIN_COOKIE_NAME, "")
    try:
        expires_at, signature = token.split(":", 1)
        if int(expires_at) < int(time.time()):
            raise ValueError
    except ValueError:
        raise HTTPException(status_code=401, detail="Admin password required") from None
    expected = hmac.new(_embed_admin_secret(), expires_at.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="Admin password required")


def _embed_admin_secret() -> bytes:
    return (settings.notion_token or settings.notion_database_id or ADMIN_PASSWORD).encode("utf-8")
