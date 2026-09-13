"""Attach Zhihu sources to graph nodes: search → dedupe → read full text.

Network work (search, page reads) runs in a thread pool; all database writes happen on the calling thread,
so a single SQLAlchemy session is enough and there are no cross-thread races on the ``sources`` table.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Node, NodeSource, Source, utcnow
from app.services.cache import cache_get, cache_set
from app.services.prompts import KIND_LABEL
from app.zhihu.models import PageContent, SearchHit
from app.zhihu.reader import PageReader
from app.zhihu.search import ZhihuSearch

log = logging.getLogger(__name__)

SEARCH_TTL = 7 * 24 * 3600
PAGE_TTL = 30 * 24 * 3600
ProgressFn = Callable[[str, int, int], None]


def queries_for(node: Node) -> list[str]:
    queries = [q.strip() for q in (node.search_queries or []) if q and q.strip()]
    if not queries:
        queries = [node.label]
    return queries[:2]


def _safe_search(search: ZhihuSearch, query: str, limit: int) -> list[SearchHit]:
    try:
        return search.search(query, limit=limit)
    except Exception as exc:  # pragma: no cover - network
        log.warning("search failed for %r: %s", query, exc)
        return []


def _safe_fetch(reader: PageReader, url: str) -> PageContent:
    try:
        return reader.fetch(url)
    except Exception as exc:  # pragma: no cover - network
        return PageContent(url=url, ok=False, error=str(exc)[:200])


def upsert_source(db: Session, hit: SearchHit) -> Source:
    source = db.query(Source).filter(Source.url == hit.url).one_or_none()
    if source is None:
        source = Source(url=hit.url, kind=hit.kind, title=hit.title, snippet=hit.snippet, origin="official" if hit.backend == "official" else "web")
        db.add(source)
        db.flush()
    else:
        if hit.title and not source.title:
            source.title = hit.title
        if hit.snippet and len(hit.snippet) > len(source.snippet or ""):
            source.snippet = hit.snippet
    return source


def attach(db: Session, node: Node, source: Source, rank: int, query: str) -> None:
    exists = db.query(NodeSource).filter(NodeSource.node_id == node.id, NodeSource.source_id == source.id).one_or_none()
    if exists is None:
        db.add(NodeSource(node_id=node.id, source_id=source.id, rank=rank, query=query))


def ground_nodes(
    db: Session,
    nodes: list[Node],
    search: ZhihuSearch,
    reader: PageReader,
    settings: Settings,
    on_progress: ProgressFn | None = None,
) -> dict[str, int]:
    """Ground a batch of nodes. Returns ``{node_id: number_of_sources}``."""
    report = on_progress or (lambda *_: None)
    limit = settings.sources_per_node
    workers = max(1, settings.grounding_concurrency)

    # ---- phase A: searches (cache first, then network in parallel).
    # Round 1 uses each node's best query; round 2 only re-queries nodes that came back thin,
    # which keeps us well under the anonymous rate limits of the web-search fallbacks.
    results: dict[tuple[str, str], list[SearchHit]] = {}
    total = len(nodes) + sum(1 for n in nodes if len(queries_for(n)) > 1)
    done = 0

    def run_round(tasks: list[tuple[Node, str]]) -> None:
        nonlocal done
        pending: list[tuple[Node, str]] = []
        for node, query in tasks:
            cached = cache_get(db, f"search:v1:{query}", SEARCH_TTL)
            if cached is not None:
                results[(node.id, query)] = [SearchHit.from_dict(h) for h in cached][:limit]
                done += 1
            else:
                pending.append((node, query))
        report("search", done, total)
        if not pending:
            return
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for (node, query), hits in zip(pending, pool.map(lambda t: _safe_search(search, t[1], limit), pending)):
                results[(node.id, query)] = hits
                if hits:
                    cache_set(db, f"search:v1:{query}", [h.to_dict() for h in hits])
                done += 1
                report("search", done, total)

    run_round([(node, queries_for(node)[0]) for node in nodes])
    thin = [(node, queries_for(node)[1]) for node in nodes if len(queries_for(node)) > 1 and len(results.get((node.id, queries_for(node)[0]), [])) < 2]
    done += sum(1 for n in nodes if len(queries_for(n)) > 1) - len(thin)  # skipped second queries count as done
    if thin:
        run_round(thin)
    report("search", total, total)

    # ---- phase B: attach the best hits to each node
    counts: dict[str, int] = {}
    read_plan: list[Source] = []
    for node in nodes:
        merged: list[tuple[SearchHit, str]] = []
        seen: set[str] = set()
        for query in queries_for(node):
            for hit in results.get((node.id, query), []):
                if hit.url not in seen:
                    seen.add(hit.url)
                    merged.append((hit, query))
        merged = merged[:limit]
        for rank, (hit, query) in enumerate(merged):
            source = upsert_source(db, hit)
            attach(db, node, source, rank, query)
            if hit.content and not source.content:
                source.content = hit.content
                source.fetched_at = utcnow()
            if rank < settings.fetch_full_text_per_node and not source.content and source not in read_plan:
                read_plan.append(source)
        node.grounding_status = "done" if merged else "failed"
        counts[node.id] = len(merged)
    db.commit()

    # ---- phase C: read full text for the top sources (cache first, then network in parallel)
    pending_sources: list[Source] = []
    for source in read_plan:
        cached = cache_get(db, f"page:v1:{source.url}", PAGE_TTL)
        if cached is not None:
            _apply_page(source, PageContent.from_dict(cached))
        else:
            pending_sources.append(source)
    total = len(read_plan)
    done = total - len(pending_sources)
    report("read", done, total)
    if pending_sources:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for source, page in zip(pending_sources, pool.map(lambda s: _safe_fetch(reader, s.url), pending_sources)):
                if page.ok and page.text:
                    cache_set(db, f"page:v1:{source.url}", page.to_dict())
                _apply_page(source, page)
                done += 1
                report("read", done, total)
    db.commit()
    return counts


def _apply_page(source: Source, page: PageContent) -> None:
    if page.ok and page.text:
        source.content = page.text
        source.fetched_at = utcnow()
        if page.title and (not source.title or source.title == source.url):
            source.title = page.title
        if page.author:
            source.author = page.author
        if page.votes:
            source.votes = page.votes
    else:
        source.meta = {**(source.meta or {}), "fetch_error": page.error}


def source_context(node: Node, per_source_chars: int = 3500, total_chars: int = 14000) -> tuple[str, list[dict[str, Any]]]:
    """Numbered source block for prompts + citation metadata for the UI."""
    parts: list[str] = []
    citations: list[dict[str, Any]] = []
    used = 0
    for index, link in enumerate(node.sources, start=1):
        source = link.source
        body = (source.content or "").strip() or (source.snippet or "").strip()
        body = body[:per_source_chars]
        if used + len(body) > total_chars:
            body = body[: max(0, total_chars - used)]
        used += len(body)
        title = source.title or source.url
        parts.append(f"[{index}] {title}（{KIND_LABEL.get(source.kind, '知乎页面')}）\n链接：{source.url}\n内容：{body or '（仅有标题）'}")
        citations.append({"index": index, "title": title, "url": source.url, "kind": source.kind, "source_id": source.id})
    if not parts:
        return "（本知识点暂未关联到知乎来源；请基于通用知识讲解，并在开头用一句话说明缺少来源。）", citations
    return "\n\n".join(parts), citations
