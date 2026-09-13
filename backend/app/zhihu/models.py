from __future__ import annotations

import re
import urllib.parse
from dataclasses import asdict, dataclass, field
from typing import Any

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


@dataclass
class SearchHit:
    url: str
    title: str
    snippet: str = ""
    kind: str = "other"  # question | answer | article | other
    backend: str = "web"
    rank: int = 0
    content: str = ""  # full text when the backend already returns it (e.g. Jina search)
    votes: int = 0
    author: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SearchHit":
        return cls(
            **{k: data.get(k, "") for k in ("url", "title", "snippet", "kind", "backend", "content", "author")},
            rank=int(data.get("rank", 0)),
            votes=int(data.get("votes", 0) or 0),
            meta=data.get("meta") or {},
        )


@dataclass
class PageContent:
    url: str
    title: str = ""
    text: str = ""
    author: str = ""
    votes: int = 0
    ok: bool = True
    error: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PageContent":
        return cls(
            url=data.get("url", ""),
            title=data.get("title", ""),
            text=data.get("text", ""),
            author=data.get("author", ""),
            votes=int(data.get("votes", 0) or 0),
            ok=bool(data.get("ok", True)),
            error=data.get("error", ""),
            meta=data.get("meta") or {},
        )


_ANSWER_RE = re.compile(r"^/question/(\d+)/answer/(\d+)$")
_ANSWER_SHORT_RE = re.compile(r"^/answer/(\d+)$")
_QUESTION_RE = re.compile(r"^/question/(\d+)$")
_ARTICLE_RE = re.compile(r"^/p/(\d+)$")


def classify_zhihu_url(url: str) -> tuple[str, str] | None:
    """Return ``(kind, canonical_url)`` for a Zhihu content URL, or ``None`` for non-content pages."""
    try:
        parts = urllib.parse.urlsplit(url.strip())
    except ValueError:
        return None
    host = parts.netloc.lower()
    if not (host == "zhihu.com" or host.endswith(".zhihu.com")):
        return None
    path = parts.path.rstrip("/")
    m = _ANSWER_RE.match(path)
    if m:
        return "answer", f"https://www.zhihu.com/question/{m.group(1)}/answer/{m.group(2)}"
    m = _ANSWER_SHORT_RE.match(path)
    if m:
        return "answer", f"https://www.zhihu.com/answer/{m.group(1)}"
    m = _QUESTION_RE.match(path)
    if m:
        return "question", f"https://www.zhihu.com/question/{m.group(1)}"
    m = _ARTICLE_RE.match(path)
    if m:
        return "article", f"https://zhuanlan.zhihu.com/p/{m.group(1)}"
    return None


def clean_title(title: str) -> str:
    title = re.sub(r"\s+", " ", title).strip()
    for suffix in (" - 知乎", " - 知乎专栏", "- 知乎", "-知乎", " | 知乎"):
        if title.endswith(suffix):
            title = title[: -len(suffix)].strip()
    return title
