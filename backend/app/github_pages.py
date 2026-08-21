from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path

import httpx

from .config import Settings


@dataclass(frozen=True)
class PagesPublishResult:
    html_url: str
    commit_sha: str
    content_sha: str


async def publish_embed_html_to_github_pages(settings: Settings, html_path: Path) -> PagesPublishResult:
    token = settings.github_pages_token
    if not token:
        raise RuntimeError("GITHUB_PAGES_TOKEN is not configured")

    content = html_path.read_text(encoding="utf-8")
    api_url = (
        f"https://api.github.com/repos/{settings.github_pages_owner}/"
        f"{settings.github_pages_repo}/contents/{settings.github_pages_path}"
    )
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "notion-daily-defect-dashboard",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    async with httpx.AsyncClient(headers=headers, timeout=httpx.Timeout(30.0, connect=10.0)) as client:
        current = await client.get(api_url, params={"ref": settings.github_pages_branch})
        current.raise_for_status()
        current_data = current.json()
        payload = {
            "message": "Update defect dashboard snapshot",
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
            "sha": current_data["sha"],
            "branch": settings.github_pages_branch,
        }
        updated = await client.put(api_url, json=payload)
        updated.raise_for_status()
        updated_data = updated.json()

    return PagesPublishResult(
        html_url=updated_data["content"]["html_url"],
        commit_sha=updated_data["commit"]["sha"],
        content_sha=updated_data["content"]["sha"],
    )
