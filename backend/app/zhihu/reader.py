"""Fetch the text of a Zhihu page through a reader proxy (Jina Reader by default).

Zhihu serves a verification page to anonymous scripted clients; Jina Reader renders the page in a
real browser and returns Markdown, which is enough for grounding lessons and citing sources.
"""
from __future__ import annotations

import logging
import os
import re

import httpx

from app.zhihu.models import PageContent, clean_title

log = logging.getLogger(__name__)

_BLOCK_MARKERS = ("安全验证", "系统监测到您的网络环境存在异常", "请点击下方验证按钮", "unhuman", "请求参数异常")
_NOISE_LINE_RE = re.compile(
    r"^(\[!\[|!\[|\[关注\]|\[推荐\]|\[热榜\]|\[专栏\]|\[直答\]|\[\]\(|切换模式|登录/注册|关注问题|写回答|​邀请回答|​好问题|​分享|Comments|Go to the first comment|\[.*?\]\(https://www\.zhihu\.com/signin)"
)


def _clean_markdown(text: str) -> str:
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.replace("​", "").rstrip()
        if not line.strip():
            if lines and lines[-1] != "":
                lines.append("")
            continue
        if _NOISE_LINE_RE.match(line.strip()):
            continue
        line = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", line)  # drop images
        line = re.sub(r"\[([^\]]+)\]\((https?://[^)]*zhihu\.com[^)]*)\)", r"\1", line)  # unwrap internal links
        if line.strip():
            lines.append(line)
    cleaned = "\n".join(lines).strip()
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


def parse_reader_response(url: str, body: str) -> PageContent:
    title_m = re.search(r"^Title:\s*(.*)$", body, re.M)
    title = clean_title(title_m.group(1)) if title_m else ""
    content = body.split("Markdown Content:", 1)[1] if "Markdown Content:" in body else body
    if any(marker in body[:4000] for marker in _BLOCK_MARKERS) and len(content) < 3000:
        return PageContent(url=url, title=title, ok=False, error="页面需要验证，未能读取正文")
    if "Warning: Target URL returned error" in body[:600]:
        return PageContent(url=url, title=title, ok=False, error="目标页面返回错误")
    text = _clean_markdown(content)
    votes = 0
    m = re.search(r"赞同\s*([\d,]+)", content)
    if m:
        votes = int(m.group(1).replace(",", ""))
    author = ""
    m = re.search(r"\n([^\n]{1,40})\n\n[^\n]{0,80}\n\n[^\n]*赞同", content)
    if m:
        author = m.group(1).strip("* ")
    return PageContent(url=url, title=title, text=text, author=author, votes=votes, ok=bool(text))


class PageReader:
    def __init__(self, base: str = "https://r.jina.ai", api_key: str | None = None, timeout: float = 45.0, max_chars: int = 12000) -> None:
        self.base = base.rstrip("/")
        self.api_key = api_key if api_key is not None else os.environ.get("JINA_API_KEY", "")
        self.timeout = timeout
        self.max_chars = max_chars

    def fetch(self, url: str) -> PageContent:
        # NOTE: a browser-like User-Agent makes the reader's edge return a 403 challenge page; keep a plain UA.
        headers = {"User-Agent": "learnpath/0.1 (+https://github.com)", "Accept": "text/plain", "X-Timeout": "25"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                resp = client.get(f"{self.base}/{url}", headers=headers)
        except httpx.HTTPError as exc:
            return PageContent(url=url, ok=False, error=f"读取失败: {exc}")
        if resp.status_code == 429:
            return PageContent(url=url, ok=False, error="reader 限流")
        if resp.status_code >= 400:
            return PageContent(url=url, ok=False, error=f"reader http {resp.status_code}")
        page = parse_reader_response(url, resp.text)
        if len(page.text) > self.max_chars:
            page.text = page.text[: self.max_chars] + "\n\n（正文过长，已截断）"
        return page
