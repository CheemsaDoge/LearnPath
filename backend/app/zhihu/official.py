"""Adapter for 知乎数据开放平台 (the official data platform that backs the hackathon).

The hackathon organisers issue credentials and endpoint documentation to registered teams. This module is the
single place where those endpoints are wired in; everything else in LearnWay only talks to ``ZhihuOpenPlatform``.

Until real credentials are configured (``LEARNWAY_ZHIHU_OPEN_API_BASE`` / ``LEARNWAY_ZHIHU_OPEN_API_KEY``),
``configured`` is ``False`` and callers fall back to the web-search + reader pipeline.

The request/response mapping below assumes a conventional JSON shape (``{"data": [{"url", "title", "excerpt"}]}``).
Adjust ``_map_hit`` and the paths once the official handbook for your team is available — no other code changes.
"""
from __future__ import annotations

import httpx

from app.zhihu.models import SearchHit


class NotConfigured(RuntimeError):
    pass


class ZhihuOpenPlatform:
    def __init__(self, base: str = "", api_key: str = "", timeout: float = 20.0) -> None:
        self.base = base.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.base and self.api_key)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}

    @staticmethod
    def _map_hit(item: dict) -> SearchHit | None:
        url = item.get("url") or item.get("link")
        if not url:
            return None
        return SearchHit(
            url=url,
            title=item.get("title", ""),
            snippet=item.get("excerpt") or item.get("snippet") or item.get("content", "")[:200],
            backend="official",
        )

    def search(self, query: str, limit: int = 6) -> list[SearchHit]:
        if not self.configured:
            raise NotConfigured("知乎数据开放平台未配置")
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(f"{self.base}/search", params={"q": query, "limit": limit}, headers=self._headers())
        resp.raise_for_status()
        payload = resp.json()
        rows = payload.get("data") if isinstance(payload, dict) else payload
        hits = [self._map_hit(row) for row in rows or []]
        return [h for h in hits if h]
