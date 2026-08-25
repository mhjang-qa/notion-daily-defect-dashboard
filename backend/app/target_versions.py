from __future__ import annotations

import re


HANPASS_RENEWAL_NATIVE = "[Hanpass][앱개편][Native]"
HANPASS_RENEWAL_BO = "[Hanpass][앱개편][BO]"
HANPASS_RENEWAL_PLANNING = "[Hanpass][앱개편][기획]"
LEGACY_HANPASS_RENEWAL_NATIVE = "[Hanpass][앱개편]"

HANPASS_RENEWAL_TARGET_VERSIONS = [
    HANPASS_RENEWAL_NATIVE,
    HANPASS_RENEWAL_BO,
    HANPASS_RENEWAL_PLANNING,
]

_ALIASES = {
    LEGACY_HANPASS_RENEWAL_NATIVE: HANPASS_RENEWAL_NATIVE,
}


def split_target_versions(value: str) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return []
    return [part.strip() for part in re.split(r"[,/]\s*", text) if part.strip()]


def normalize_target_version(value: str) -> str:
    text = str(value or "").strip()
    return _ALIASES.get(text, text)


def normalize_target_versions(value: str) -> list[str]:
    versions = []
    for version in split_target_versions(value):
        normalized = normalize_target_version(version)
        if normalized and normalized not in versions:
            versions.append(normalized)
    return versions


def target_version_query_values(value: str) -> list[str]:
    normalized = normalize_target_version(value)
    values = [normalized]
    for alias, target in _ALIASES.items():
        if target == normalized and alias not in values:
            values.append(alias)
    return values


def sort_target_versions(values: list[str]) -> list[str]:
    order = {version: index for index, version in enumerate(HANPASS_RENEWAL_TARGET_VERSIONS)}

    def key(value: str):
        if value in order:
            return (0, order[value], "")
        chunks = re.split(r"(\d+)", value)
        return (1, len(order), [int(chunk) if chunk.isdigit() else chunk.lower() for chunk in chunks])

    return sorted(values, key=key)
