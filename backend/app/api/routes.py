from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import PlainTextResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.llm.base import LLMError
from app.llm.factory import get_llm
from app.models import CardDeck, ChatMessage, Edge, Graph, Node, Quiz
from app.schemas import (
    CardsOut,
    ChatMessageOut,
    ChatRequest,
    EdgeOut,
    EvidenceOut,
    GoalCreate,
    GraphCreated,
    GraphOut,
    HealthOut,
    HotItem,
    LessonOut,
    NodeDetailOut,
    NodeOut,
    QuizOut,
    QuizQuestionOut,
    QuizResultOut,
    QuizSubmit,
    SourceOut,
)
from app.services import graph_builder
from app.services.cache import cache_get, cache_set
from app.services.deps import get_official
from app.services.learning import LearningService, export_markdown
from app.services.progress import GraphProgress
from app.zhihu.hot import fetch_hot_list

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


# ----------------------------------------------------------------------------- helpers
def _graph_or_404(db: Session, graph_id: str) -> Graph:
    graph = db.get(Graph, graph_id)
    if graph is None:
        raise HTTPException(404, "图谱不存在")
    return graph


def _node_or_404(db: Session, node_id: str) -> Node:
    node = db.get(Node, node_id)
    if node is None:
        raise HTTPException(404, "知识点不存在")
    return node


def _purge_graph_content(db: Session, graph: Graph) -> None:
    """Delete everything hanging off a graph's nodes (FK-safe order), leaving the graph row itself."""
    node_ids = [n.id for n in graph.nodes]
    if node_ids:
        for model in (Quiz, CardDeck, ChatMessage):
            db.query(model).filter(model.node_id.in_(node_ids)).delete(synchronize_session=False)
    db.query(Edge).filter(Edge.graph_id == graph.id).delete(synchronize_session=False)
    db.flush()
    for node in list(graph.nodes):
        db.delete(node)
    db.flush()


def _node_out(node: Node, progress: GraphProgress) -> NodeOut:
    out = NodeOut.model_validate(node)
    out.source_count = len(node.sources)
    out.unlocked = progress.is_unlocked(node)
    if not progress.is_learnable(node):
        out.mastery_stars = progress.stars(node)
    return out


def _graph_out(graph: Graph) -> GraphOut:
    progress = GraphProgress(graph)
    out = GraphOut.model_validate(graph)
    out.goal_text = graph.goal.raw_goal
    out.nodes = [_node_out(n, progress) for n in graph.nodes]
    out.edges = [EdgeOut.model_validate(e) for e in graph.edges]
    if graph.status in {"ready", "grounding"}:
        out.stats = progress.stats()
        out.next_actions = progress.next_actions()
    return out


def _sse(events: Iterator[dict[str, Any]]) -> StreamingResponse:
    def generate() -> Iterator[str]:
        try:
            for event in events:
                yield "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"
        except LLMError as exc:
            yield "data: " + json.dumps({"error": str(exc)}, ensure_ascii=False) + "\n\n"
        except Exception as exc:  # pragma: no cover - defensive
            log.exception("stream failed")
            yield "data: " + json.dumps({"error": f"服务端错误：{exc}"}, ensure_ascii=False) + "\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _llm_error(exc: LLMError) -> HTTPException:
    return HTTPException(502, str(exc))


# ----------------------------------------------------------------------------- meta
@router.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    settings = get_settings()
    llm = get_llm()
    return HealthOut(
        status="ok",
        llm_provider=llm.name,
        llm_model=llm.model,
        zhihu_search=settings.search_backend_list,
        zhihu_official=get_official().configured,
        reader=settings.reader_base,
        zhihu_oauth="enabled(test)" if settings.zhihu_oauth_enabled else "disabled",
    )


@router.get("/hot", response_model=list[HotItem])
def hot_list(db: Session = Depends(get_db)) -> list[HotItem]:
    cached = cache_get(db, "hot:v1", max_age_seconds=600)
    if cached is None:
        try:
            cached = fetch_hot_list(limit=30)
        except Exception as exc:
            log.warning("hot list unavailable: %s", exc)
            stale = cache_get(db, "hot:v1")
            if stale is None:
                raise HTTPException(503, "知乎热榜暂时不可用") from exc
            cached = stale
        else:
            cache_set(db, "hot:v1", cached)
    return [HotItem(**item) for item in cached]


# ----------------------------------------------------------------------------- graphs
@router.post("/goals", response_model=GraphCreated, status_code=201)
def create_goal(payload: GoalCreate, db: Session = Depends(get_db)) -> GraphCreated:
    graph = graph_builder.create_goal_graph(db, payload)
    graph_builder.start_pipeline(graph.id)
    return GraphCreated(graph_id=graph.id, goal_id=graph.goal_id, status=graph.status)


@router.get("/graphs", response_model=list[GraphOut])
def list_graphs(db: Session = Depends(get_db)) -> list[GraphOut]:
    graphs = db.query(Graph).order_by(Graph.created_at.desc()).limit(30).all()
    outs: list[GraphOut] = []
    for graph in graphs:
        progress = GraphProgress(graph)
        out = GraphOut.model_validate(graph)
        out.goal_text = graph.goal.raw_goal
        if graph.status == "ready":
            out.stats = progress.stats()
        outs.append(out)
    return outs


@router.get("/graphs/{graph_id}", response_model=GraphOut)
def get_graph(graph_id: str, db: Session = Depends(get_db)) -> GraphOut:
    return _graph_out(_graph_or_404(db, graph_id))


@router.delete("/graphs/{graph_id}", status_code=204)
def delete_graph(graph_id: str, db: Session = Depends(get_db)) -> Response:
    graph = _graph_or_404(db, graph_id)
    _purge_graph_content(db, graph)
    db.delete(graph)
    db.commit()
    return Response(status_code=204)


@router.post("/graphs/{graph_id}/retry", response_model=GraphCreated)
def retry_graph(graph_id: str, db: Session = Depends(get_db)) -> GraphCreated:
    graph = _graph_or_404(db, graph_id)
    if graph.status not in {"failed", "ready", "grounding"}:
        raise HTTPException(409, "图谱正在生成中")
    _purge_graph_content(db, graph)
    graph.status = "generating"
    graph.error = ""
    graph.progress = {"step": "plan", "done": 0, "total": 0}
    db.commit()
    graph_builder.start_pipeline(graph.id)
    return GraphCreated(graph_id=graph.id, goal_id=graph.goal_id, status=graph.status)


@router.get("/graphs/{graph_id}/export.md", response_class=PlainTextResponse)
def export_graph(graph_id: str, db: Session = Depends(get_db)) -> PlainTextResponse:
    graph = _graph_or_404(db, graph_id)
    return PlainTextResponse(export_markdown(graph), media_type="text/markdown; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="learnway-{graph.id}.md"'})


# ----------------------------------------------------------------------------- nodes
@router.get("/nodes/{node_id}", response_model=NodeDetailOut)
def node_detail(node_id: str, db: Session = Depends(get_db)) -> NodeDetailOut:
    node = _node_or_404(db, node_id)
    progress = GraphProgress(node.graph)
    service = LearningService(db, get_llm())
    base = _node_out(node, progress)
    sources: list[SourceOut] = []
    for link in node.sources:
        s = SourceOut.model_validate(link.source)
        s.has_content = bool(link.source.content)
        sources.append(s)
    lesson = service.latest_lesson(node)
    deck = service.latest_cards(node)
    chat = db.query(ChatMessage).filter(ChatMessage.node_id == node.id).order_by(ChatMessage.created_at.asc()).all()
    return NodeDetailOut(
        **base.model_dump(),
        teaching_strategy=node.teaching_strategy,
        search_queries=list(node.search_queries or []),
        sources=sources,
        lesson=LessonOut.model_validate(lesson) if lesson else None,
        evidence=[EvidenceOut.model_validate(e) for e in sorted(node.evidence, key=lambda e: e.created_at, reverse=True)[:20]],
        chat=[ChatMessageOut.model_validate(m) for m in chat],
        cards=deck.cards if deck else None,
        prerequisites=[{"id": p.id, "label": p.label, "satisfied": progress.prereq_satisfied(p)} for p in progress.prereqs.get(node.id, [])],
    )


@router.post("/nodes/{node_id}/lesson")
def stream_lesson(node_id: str, db: Session = Depends(get_db)) -> StreamingResponse:
    node = _node_or_404(db, node_id)
    return _sse(LearningService(db, get_llm()).stream_lesson(node))


@router.post("/nodes/{node_id}/quiz", response_model=QuizOut)
def create_quiz(node_id: str, db: Session = Depends(get_db)) -> QuizOut:
    node = _node_or_404(db, node_id)
    try:
        quiz = LearningService(db, get_llm()).generate_quiz(node)
    except LLMError as exc:
        raise _llm_error(exc) from exc
    return QuizOut(id=quiz.id, node_id=node.id, questions=[QuizQuestionOut(id=q["id"], qtype=q["qtype"], stem=q["stem"], options=q["options"], source_index=q["source_index"]) for q in quiz.questions])


@router.post("/quizzes/{quiz_id}/submit", response_model=QuizResultOut)
def submit_quiz(quiz_id: str, payload: QuizSubmit, db: Session = Depends(get_db)) -> QuizResultOut:
    quiz = db.get(Quiz, quiz_id)
    if quiz is None:
        raise HTTPException(404, "测验不存在")
    if quiz.submitted:
        raise HTTPException(409, "这份测验已经提交过了，请重新生成一份")
    try:
        return LearningService(db, get_llm()).grade_quiz(quiz, payload.answers)
    except LLMError as exc:
        raise _llm_error(exc) from exc


@router.post("/nodes/{node_id}/cards", response_model=CardsOut)
def create_cards(node_id: str, db: Session = Depends(get_db)) -> CardsOut:
    node = _node_or_404(db, node_id)
    try:
        deck = LearningService(db, get_llm()).generate_cards(node)
    except LLMError as exc:
        raise _llm_error(exc) from exc
    return CardsOut(node_id=node.id, cards=deck.cards)


@router.post("/nodes/{node_id}/chat")
def stream_chat(node_id: str, payload: ChatRequest, db: Session = Depends(get_db)) -> StreamingResponse:
    node = _node_or_404(db, node_id)
    return _sse(LearningService(db, get_llm()).stream_chat(node, payload.question))


@router.post("/nodes/{node_id}/ground", response_model=NodeDetailOut)
def reground(node_id: str, db: Session = Depends(get_db)) -> NodeDetailOut:
    node = _node_or_404(db, node_id)
    graph_builder.reground_node(db, node)
    db.refresh(node)
    return node_detail(node_id, db)
