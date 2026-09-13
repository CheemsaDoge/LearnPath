"""知乎数据开放平台 (https://developer.zhihu.com) — official content APIs.

Auth: ``Authorization: Bearer <Access Secret>`` + ``X-Request-Timestamp`` (unix seconds). Every endpoint returns
``{"Code": 0, "Message": "success", "Data": ...}``; non-zero ``Code`` means failure (20001 auth, 30001 rate/quota).

Endpoints used by LearnPath (see docs/zhihu-open-platform.md for quotas and caching policy):
  GET  /api/v1/content/zhihu_search        — site search (Count ≤ 10)
  GET  /api/v1/content/hot_list            — hot list (Limit ≤ 30)
  GET  /api/v1/content/question_answers    — answer summaries under a question
  POST /v1/chat/completions                — 知乎直答 (OpenAI-compatible, models zhida-fast-1p5 / zhida-thinking-1p5 / zhida-agent)
  GET  /api/v1/quota                       — remaining daily quota
"""
from __future__ import annotations

import json
import re
import time
from collections.abc import Iterator
from typing import Any

import httpx

from app.zhihu.models import SearchHit, clean_title

BASE = "https://developer.zhihu.com"
ZHIDA_MODELS = ("zhida-fast-1p5", "zhida-thinking-1p5", "zhida-agent")


class NotConfigured(RuntimeError):
    pass


class OpenPlatformError(RuntimeError):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(f"知乎开放平台错误 {code}: {message}")
        self.code = code


def _strip_em(text: str) -> str:
    return re.sub(r"</?em>", "", text or "")


def _kind(content_type: str) -> str:
    return {"answer": "answer", "article": "article", "question": "question"}.get((content_type or "").lower(), "other")


class ZhihuOpenPlatform:
    def __init__(self, access_secret: str = "", timeout: float = 30.0) -> None:
        self.access_secret = access_secret.strip()
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.access_secret)

    # ------------------------------------------------------------------ transport
    def _headers(self) -> dict[str, str]:
        if not self.configured:
            raise NotConfigured("知乎数据开放平台未配置 Access Secret")
        return {
            "Authorization": f"Bearer {self.access_secret}",
            "X-Request-Timestamp": str(int(time.time())),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _get(self, path: str, params: dict[str, Any]) -> Any:
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(BASE + path, params=params, headers=self._headers())
        if resp.status_code >= 400:
            raise OpenPlatformError(resp.status_code, resp.text[:200])
        payload = resp.json()
        if payload.get("Code", 0) != 0:
            raise OpenPlatformError(int(payload.get("Code", -1)), str(payload.get("Message", ""))[:200])
        return payload.get("Data")

    # ------------------------------------------------------------------ content
    def search(self, query: str, limit: int = 6) -> list[SearchHit]:
        data = self._get("/api/v1/content/zhihu_search", {"Query": query, "Count": max(1, min(10, limit))}) or {}
        hits: list[SearchHit] = []
        for item in data.get("Items", []):
            url = item.get("Url") or ""
            if not url:
                continue
            hits.append(
                SearchHit(
                    url=url,
                    title=clean_title(item.get("Title", "")),
                    snippet=_strip_em(item.get("ContentText", ""))[:1500],
                    kind=_kind(item.get("ContentType", "")),
                    backend="official",
                    votes=int(item.get("VoteUpCount") or 0),
                    author=item.get("AuthorName", "") or "",
                    meta={"authority_level": item.get("AuthorityLevel", ""), "tracking_url": url, "content_id": item.get("ContentID", "")},
                )
            )
        return hits

    def hot(self, limit: int = 30) -> list[dict[str, Any]]:
        data = self._get("/api/v1/content/hot_list", {"Limit": max(1, min(30, limit))}) or {}
        items: list[dict[str, Any]] = []
        for item in data.get("Items", []):
            url = item.get("Url", "")
            m = re.search(r"/(?:question|p)/(\d+)", url)
            items.append(
                {
                    "id": m.group(1) if m else url,
                    "title": (item.get("Title") or "").strip(),
                    "heat": "",
                    "excerpt": (item.get("Summary") or "").strip(),
                    "url": url,
                    "answer_count": 0,
                    "follower_count": 0,
                    "thumbnail": item.get("ThumbnailUrl", ""),
                }
            )
        return [i for i in items if i["title"]]

    def question_answers(self, question_url: str, limit: int = 10) -> list[dict[str, Any]]:
        data = self._get("/api/v1/content/question_answers", {"QuestionUrl": question_url, "Limit": max(1, min(50, limit))}) or {}
        return [{"url": i.get("Url", ""), "summary": i.get("Summary", ""), "content_type": i.get("ContentType", "")} for i in data.get("Items", [])]

    def quota(self) -> list[dict[str, Any]]:
        return self._get("/api/v1/quota", {}) or []

    # ------------------------------------------------------------------ 知乎直答
    def zhida_stream(self, messages: list[dict[str, str]], model: str = "zhida-fast-1p5") -> Iterator[dict[str, str]]:
        """Yield ``{"reasoning": ...}`` / ``{"content": ...}`` deltas from 知乎直答."""
        body = {"model": model if model in ZHIDA_MODELS else ZHIDA_MODELS[0], "messages": messages, "stream": True}
        with httpx.Client(timeout=httpx.Timeout(120.0, connect=20.0)) as client:
            with client.stream("POST", BASE + "/v1/chat/completions", headers=self._headers(), json=body) as resp:
                if resp.status_code >= 400:
                    raise OpenPlatformError(resp.status_code, resp.read().decode("utf-8", "ignore")[:200])
                for line in resp.iter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if payload == "[DONE]":
                        break
                    try:
                        event = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    if event.get("error"):
                        raise OpenPlatformError(500, str(event["error"].get("message", "直答返回错误")))
                    for choice in event.get("choices", []):
                        delta = choice.get("delta") or {}
                        if delta.get("reasoning_content"):
                            yield {"reasoning": delta["reasoning_content"]}
                        if delta.get("content"):
                            yield {"content": delta["content"]}
