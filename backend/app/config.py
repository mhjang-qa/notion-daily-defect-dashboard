from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field


ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = Path(__file__).resolve().parents[1]


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_dotenv(ROOT_DIR / ".env")
load_dotenv(BACKEND_DIR / ".env")


class Settings(BaseModel):
    notion_token: str = Field(default="", alias="NOTION_TOKEN")
    notion_database_id: str = Field(default="", alias="NOTION_DATABASE_ID")
    notion_version: str = Field(default="2022-06-28", alias="NOTION_VERSION")
    database_url: str = Field(
        default=f"sqlite:///{BACKEND_DIR / 'data' / 'defects.db'}",
        alias="DATABASE_URL",
    )
    scheduler_enabled: bool = Field(default=True, alias="SCHEDULER_ENABLED")
    scheduler_hour: int = Field(default=8, alias="SCHEDULER_HOUR")
    scheduler_minute: int = Field(default=30, alias="SCHEDULER_MINUTE")
    timezone: str = Field(default="Asia/Seoul", alias="APP_TIMEZONE")
    cors_origins: str = Field(
        default=(
            "http://127.0.0.1:5173,"
            "http://localhost:5173,"
            "https://mhjang-qa.github.io,"
            "https://automated-report-generation-dh2g.onrender.com"
        ),
        alias="CORS_ORIGINS",
    )
    frontend_dist: str = Field(default=str(ROOT_DIR / "frontend" / "dist"), alias="FRONTEND_DIST")
    render_public_origin: str = Field(
        default="https://notion-daily-defect-dashboard.onrender.com",
        alias="RENDER_PUBLIC_ORIGIN",
    )
    github_pages_token: str = Field(default="", alias="GITHUB_PAGES_TOKEN")
    github_pages_owner: str = Field(default="mhjang-qa", alias="GITHUB_PAGES_OWNER")
    github_pages_repo: str = Field(default="Automated-Report-Generation-", alias="GITHUB_PAGES_REPO")
    github_pages_branch: str = Field(default="main", alias="GITHUB_PAGES_BRANCH")
    github_pages_path: str = Field(
        default="docs/defect-dashboard/hanpass-renewal.html",
        alias="GITHUB_PAGES_PATH",
    )
    github_pages_url: str = Field(
        default="https://mhjang-qa.github.io/Automated-Report-Generation-/defect-dashboard/hanpass-renewal.html",
        alias="GITHUB_PAGES_URL",
    )

    @classmethod
    def from_env(cls) -> "Settings":
        values = {field.alias: os.environ.get(field.alias, field.default) for field in cls.model_fields.values()}
        if not values["GITHUB_PAGES_TOKEN"]:
            values["GITHUB_PAGES_TOKEN"] = os.environ.get("GITHUB_TOKEN") or os.environ.get("GITHUB_PAT") or ""
        values["SCHEDULER_ENABLED"] = str(values["SCHEDULER_ENABLED"]).lower() not in {"0", "false", "no", "off"}
        values["SCHEDULER_HOUR"] = int(values["SCHEDULER_HOUR"])
        values["SCHEDULER_MINUTE"] = int(values["SCHEDULER_MINUTE"])
        return cls.model_validate(values)

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def frontend_dist_path(self) -> Path:
        return Path(self.frontend_dist)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()
