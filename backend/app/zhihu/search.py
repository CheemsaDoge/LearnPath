"""Zhihu content discovery.

Order of preference:
1. 知乎数据开放平台 (official, hackathon credentials) — see ``official.py``.
2. Web search restricted to ``site:zhihu.com`` (Brave HTML, Bing RSS) — no key required.
"""
from __future__ import annotations

import html
import logging
import os
import re
import threading
import time
import urllib.parse
from collections.abc import Callable

import httpx

from app.zhihu.models import USER_AGENT, SearchHit, classify_zhihu_url, clean_title

log = logging.getLogger(__name__)


class SearchBackendError(RuntimeError):
    pass


def _ensure_site_filter(query: str) -> str:
    return query if "site:zhihu.com" in query else f"site:zhihu.com {query}"


def _strip_tags(fragment: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", fragment)).strip()


# --------------------------------------------------------------------------- Brave
_BRAVE_BLOCK_RE = re.compile(r'<div class="snippet [^"]*" data-pos="\d+" data-type="web"(.*?)(?=<div class="snippet [^"]*" data-pos=|</section>|$)', re.S)
_BRAVE_HREF_RE = re.compile(r'<a href="(https?://[^"]+)"')
_BRAVE_TITLE_RE = re.compile(r'<div class="title[^"]*"[^>]*>(.*?)</div>', re.S)
_BRAVE_SNIPPET_RE = re.compile(r'<div class="generic-snippet[^"]*"[^>]*>(.*?)</div>', re.S)


def parse_brave_html(page: str) -> list[SearchHit]:
    hits: list[SearchHit] = []
    for block in _BRAVE_BLOCK_RE.findall(page):
        href = _BRAVE_HREF_RE.search(block)
        if not href:
            continue
        title_m = _BRAVE_TITLE_RE.search(block)
        snippet_m = _BRAVE_SNIPPET_RE.search(block)
        hits.append(
            SearchHit(
                url=html.unescape(href.group(1)),
                title=clean_title(_strip_tags(title_m.group(1))) if title_m else "",
                snippet=_strip_tags(snippet_m.group(1)) if snippet_m else "",
                backend="brave",
            )
        )
    return hits


def brave_search(query: str, timeout: float = 25.0) -> list[SearchHit]:
    url = "https://search.brave.com/search?source=web&q=" + urllib.parse.quote(_ensure_site_filter(query))
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8", "Accept": "text/html"}
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        resp = client.get(url, headers=headers)
    if resp.status_code == 429:
        raise SearchBackendError("brave rate limited")
    if resp.status_code >= 400:
        raise SearchBackendError(f"brave http {resp.status_code}")
    hits = parse_brave_html(resp.text)
    if not hits and ("captcha" in resp.text.lower() or "unusual traffic" in resp.text.lower()):
        raise SearchBackendError("brave captcha")
    return hits


# --------------------------------------------------------------------------- Bing
_RSS_ITEM_RE = re.compile(r"<item>(.*?)</item>", re.S)


def parse_bing_rss(xml: str) -> list[SearchHit]:
    hits: list[SearchHit] = []
    for item in _RSS_ITEM_RE.findall(xml):
        link = re.search(r"<link>(.*?)</link>", item, re.S)
        title = re.search(r"<title>(.*?)</title>", item, re.S)
        desc = re.search(r"<description>(.*?)</description>", item, re.S)
        if not link:
            continue
        hits.append(
            SearchHit(
                url=html.unescape(link.group(1).strip()),
                title=clean_title(_strip_tags(title.group(1))) if title else "",
                snippet=_strip_tags(desc.group(1)) if desc else "",
                backend="bing",
            )
        )
    return hits


def bing_search(query: str, timeout: float = 25.0) -> list[SearchHit]:
    url = "https://www.bing.com/search?format=rss&setlang=zh-hans&q=" + urllib.parse.quote(_ensure_site_filter(query))
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9"}
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        resp = client.get(url, headers=headers)
    if resp.status_code >= 400:
        raise SearchBackendError(f"bing http {resp.status_code}")
    return parse_bing_rss(resp.text)


# --------------------------------------------------------------------------- 360 搜索 (anonymous, gives the real Zhihu URL in data-mdurl)
_SO_ITEM_RE = re.compile(r'<li class="res-list"(.*?)(?=<li class="res-list"|</ul>)', re.S)
_SO_URL_RE = re.compile(r'data-mdurl="([^"]+)"')
_SO_TITLE_RE = re.compile(r'<h3 class="res-title[^"]*"[^>]*>\s*<a[^>]*>(.*?)</a>', re.S)
_SO_DESC_RE = re.compile(r'<p class="res-desc">(.*?)</p>|<span class="res-list-summary">(.*?)</span>', re.S)


def parse_so360_html(page: str) -> list[SearchHit]:
    hits: list[SearchHit] = []
    for block in _SO_ITEM_RE.findall(page):
        url_m = _SO_URL_RE.search(block)
        if not url_m:
            continue
        title_m = _SO_TITLE_RE.search(block)
        desc_m = _SO_DESC_RE.search(block)
        desc = (desc_m.group(1) or desc_m.group(2) or "") if desc_m else ""
        desc = re.sub(r"^\d{4}年\d{1,2}月\d{1,2}日\s*-\s*", "", _strip_tags(desc))
        hits.append(SearchHit(url=html.unescape(url_m.group(1)), title=clean_title(_strip_tags(title_m.group(1))) if title_m else "", snippet=desc, backend="so360"))
    return hits


def so360_search(query: str, timeout: float = 25.0) -> list[SearchHit]:
    url = "https://www.so.com/s?q=" + urllib.parse.quote(_ensure_site_filter(query))
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9", "Accept": "text/html"}
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        resp = client.get(url, headers=headers)
    if resp.status_code == 429:
        raise SearchBackendError("so360 rate limited")
    if resp.status_code >= 400:
        raise SearchBackendError(f"so360 http {resp.status_code}")
    if "验证" in resp.text[:3000] and "res-list" not in resp.text:
        raise SearchBackendError("so360 captcha")
    return parse_so360_html(resp.text)


# --------------------------------------------------------------------------- Brave Search API (key)
def brave_api_search(query: str, timeout: float = 25.0) -> list[SearchHit]:
    key = os.environ.get("BRAVE_SEARCH_API_KEY", "")
    if not key:
        raise SearchBackendError("BRAVE_SEARCH_API_KEY not set")
    with httpx.Client(timeout=timeout) as client:
        resp = client.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": _ensure_site_filter(query), "count": 10, "search_lang": "zh-hans", "country": "CN"},
            headers={"Accept": "application/json", "X-Subscription-Token": key},
        )
    if resp.status_code == 429:
        raise SearchBackendError("brave api rate limited")
    if resp.status_code >= 400:
        raise SearchBackendError(f"brave api http {resp.status_code}")
    rows = (resp.json().get("web") or {}).get("results") or []
    return [SearchHit(url=r.get("url", ""), title=clean_title(r.get("title", "")), snippet=_strip_tags(r.get("description", "")), backend="brave-api") for r in rows]


# --------------------------------------------------------------------------- Jina Search (key; returns page text too)
def jina_search(query: str, timeout: float = 60.0) -> list[SearchHit]:
    key = os.environ.get("JINA_API_KEY", "")
    if not key:
        raise SearchBackendError("JINA_API_KEY not set")
    with httpx.Client(timeout=timeout) as client:
        resp = client.get(
            "https://s.jina.ai/",
            params={"q": _ensure_site_filter(query)},
            headers={"Accept": "application/json", "Authorization": f"Bearer {key}", "X-Site": "https://zhihu.com"},
        )
    if resp.status_code == 429:
        raise SearchBackendError("jina search rate limited")
    if resp.status_code >= 400:
        raise SearchBackendError(f"jina search http {resp.status_code}")
    rows = resp.json().get("data") or []
    return [SearchHit(url=r.get("url", ""), title=clean_title(r.get("title", "")), snippet=(r.get("description") or "")[:300], content=(r.get("content") or "")[:12000], backend="jina") for r in rows]


BACKENDS: dict[str, Callable[[str, float], list[SearchHit]]] = {
    "brave-api": brave_api_search,
    "jina": jina_search,
    "brave": brave_search,
    "so360": so360_search,
    "bing": bing_search,
}
KEYED_BACKENDS = {"brave-api": "BRAVE_SEARCH_API_KEY", "jina": "JINA_API_KEY"}


def available_backends(names: list[str]) -> list[str]:
    """Drop keyed backends whose key is missing so callers don't waste a round-trip."""
    return [n for n in names if n in BACKENDS and (n not in KEYED_BACKENDS or os.environ.get(KEYED_BACKENDS[n]))]


# --------------------------------------------------------------------------- facade
def normalize_hits(hits: list[SearchHit], limit: int) -> list[SearchHit]:
    """Keep only Zhihu content pages, canonicalise URLs, dedupe, rank."""
    seen: set[str] = set()
    out: list[SearchHit] = []
    for hit in hits:
        classified = classify_zhihu_url(hit.url)
        if not classified:
            continue
        kind, canonical = classified
        if canonical in seen:
            continue
        seen.add(canonical)
        hit.url = canonical
        hit.kind = kind
        if not hit.title:
            snippet = re.sub(r"\s+", " ", hit.snippet).strip(" ,.。，")
            hit.title = (snippet[:36] + "…") if len(snippet) > 36 else (snippet or {"question": "知乎问题", "answer": "知乎回答", "article": "知乎专栏文章"}.get(kind, "知乎页面"))
        hit.rank = len(out)
        out.append(hit)
        if len(out) >= limit:
            break
    return out


class ZhihuSearch:
    def __init__(self, backends: list[str], official=None, timeout: float = 25.0, pause: float = 1.2, retry_pause: float = 4.0) -> None:
        self.backends = available_backends(backends)
        self.official = official
        self.timeout = timeout
        self.pause = pause
        self.retry_pause = retry_pause
        self._last_call = 0.0
        self._lock = threading.Lock()

    def _throttle(self) -> None:
        with self._lock:
            wait = self.pause - (time.monotonic() - self._last_call)
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.monotonic()

    def search(self, query: str, limit: int = 6) -> list[SearchHit]:
        if self.official is not None and self.official.configured:
            try:
                hits = self.official.search(query, limit=limit)
                if hits:
                    return normalize_hits(hits, limit)
            except Exception as exc:  # pragma: no cover - depends on external service
                log.warning("official zhihu search failed (%s); falling back to web search", exc)
        errors: list[str] = []
        for name in self.backends:
            for attempt in range(2):
                try:
                    self._throttle()
                    hits = normalize_hits(BACKENDS[name](query, self.timeout), limit)
                    if hits:
                        return hits
                    errors.append(f"{name}: 0 zhihu hits")
                    break
                except SearchBackendError as exc:
                    errors.append(f"{name}: {exc}")
                    if attempt == 0 and ("rate limited" in str(exc) or "captcha" in str(exc)):
                        log.info("search backend %s throttled for %r; backing off", name, query)
                        time.sleep(self.retry_pause)
                        continue
                    break
                except Exception as exc:
                    errors.append(f"{name}: {exc}")
                    log.warning("search backend %s failed for %r: %s", name, query, exc)
                    break
        log.info("no zhihu hits for %r (%s)", query, "; ".join(errors))
        return []
