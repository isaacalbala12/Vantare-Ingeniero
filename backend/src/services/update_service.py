"""Comparación de versiones y consulta de releases en GitHub."""

from __future__ import annotations

import logging
import re

import httpx
from src.version import APP_VERSION, GITHUB_REPO

logger = logging.getLogger("vantare.update")


def parse_version(version: str) -> tuple[int, int, int]:
    cleaned = (version or "").strip().lstrip("v")
    parts = cleaned.split(".")
    nums: list[int] = []
    for part in parts[:3]:
        match = re.match(r"(\d+)", part or "")
        nums.append(int(match.group(1)) if match else 0)
    while len(nums) < 3:
        nums.append(0)
    return nums[0], nums[1], nums[2]


def is_newer_version(latest: str, current: str) -> bool:
    return parse_version(latest) > parse_version(current)


async def fetch_latest_release(repo: str = GITHUB_REPO) -> dict | None:
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url, headers={"Accept": "application/vnd.github+json"})
            if resp.status_code != 200:
                return None
            data = resp.json()
            tag = str(data.get("tag_name", "")).lstrip("v")
            return {
                "tag": tag,
                "name": data.get("name") or tag,
                "html_url": data.get("html_url", ""),
                "published_at": data.get("published_at", ""),
            }
    except Exception as exc:
        logger.debug("fetch_latest_release failed: %s", exc)
        return None


async def check_for_update(current_version: str = APP_VERSION) -> dict:
    release = await fetch_latest_release()
    if not release or not release.get("tag"):
        return {
            "current_version": current_version,
            "latest_version": current_version,
            "update_available": False,
            "release_url": "",
        }
    latest = release["tag"]
    return {
        "current_version": current_version,
        "latest_version": latest,
        "update_available": is_newer_version(latest, current_version),
        "release_url": release.get("html_url", ""),
        "release_name": release.get("name", latest),
    }
