from __future__ import annotations

import re

import httpx

from app.zhihu.models import USER_AGENT

HOT_LIST_URL = "https://api.zhihu.com/topstory/hot-list"


def _to_web_url(api_url: str, item_id: str) -> str:
    m = re.search(r"/questions/(\d+)", api_url or "")
    if m:
        return f"https://www.zhihu.com/question/{m.group(1)}"
    return api_url or f"https://www.zhihu.com/question/{item_id}"


def parse_hot_list(payload: dict) -> list[dict]:
    items: list[dict] = []
    for entry in payload.get("data", []):
        target = entry.get("target") or {}
        if not target.get("title"):
            continue
        item_id = str(target.get("id", ""))
        items.append(
            {
                "id": item_id,
                "title": target.get("title", "").strip(),
                "heat": entry.get("detail_text", ""),
                "excerpt": (target.get("excerpt") or "").strip(),
                "url": _to_web_url(target.get("url", ""), item_id),
                "answer_count": int(target.get("answer_count") or 0),
                "follower_count": int(target.get("follower_count") or 0),
            }
        )
    return items


def fetch_hot_list(limit: int = 30, timeout: float = 20.0) -> list[dict]:
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        resp = client.get(HOT_LIST_URL, params={"limit": limit}, headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()
    return parse_hot_list(resp.json())
