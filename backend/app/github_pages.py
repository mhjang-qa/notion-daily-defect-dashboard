from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from pathlib import Path

import httpx

from .config import Settings
from .embed_renderer import render_hanpass_renewal_embed


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
        current_content = base64.b64decode(current_data["content"]).decode("utf-8")
        content = merge_embed_html_snapshots(current_content, content)
        html_path.write_text(content, encoding="utf-8")
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


SNAPSHOT_DATA_RE = re.compile(
    r'<script id="snapshot-data" type="application/json">(.*?)</script>',
    re.DOTALL,
)


def merge_embed_html_snapshots(existing_html: str, fresh_html: str) -> str:
    existing = extract_snapshot_payload(existing_html)
    fresh = extract_snapshot_payload(fresh_html)
    if not existing or not fresh:
        return fresh_html

    versions = []
    for group in [*existing.get("groups", []), *fresh.get("groups", [])]:
        version = group.get("version")
        if version and version not in versions:
            versions.append(version)

    merged_groups = []
    for version in versions:
        rows_by_date = {}
        existing_items = []
        fresh_items = []
        for payload in (existing, fresh):
            for group in payload.get("groups", []):
                if group.get("version") != version:
                    continue
                for row in group.get("rows", []):
                    snapshot_date = row.get("snapshot_date")
                    if snapshot_date:
                        rows_by_date[snapshot_date] = row
                if payload is existing:
                    existing_items = group.get("items", []) or existing_items
                else:
                    fresh_items = group.get("items", []) or fresh_items
        merged_groups.append(
            {
                "version": version,
                "rows": normalize_cumulative_rows([rows_by_date[key] for key in sorted(rows_by_date)]),
                "items": fresh_items or existing_items,
            }
        )

    generated_at = fresh.get("generatedAt") or existing.get("generatedAt") or ""
    return render_hanpass_renewal_embed(merged_groups, generated_at)


def extract_snapshot_payload(html: str) -> dict | None:
    match = SNAPSHOT_DATA_RE.search(html)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def normalize_cumulative_rows(rows: list[dict]) -> list[dict]:
    normalized = [dict(row) for row in rows]
    for row in normalized:
        row["qa_verified_count"] = int(row.get("qa_verified_count") or 0)
    return normalized
