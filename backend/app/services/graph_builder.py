"""Goal → knowledge graph → Zhihu grounding. Runs as a background job per graph."""
from __future__ import annotations

import logging
import threading
import traceback

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import session_factory
from app.llm.base import LLMError
from app.llm.factory import get_llm
from app.llm.resilience import call_with_retries
from app.services.fallbacks import fallback_graph
from app.models import Edge, Goal, Graph, Node, User
from app.schemas import GoalCreate, LLMGraph
from app.services.deps import get_reader, get_search
from app.services import profile as profile_service
from app.services.attachments import attachment_context
from app.services.grounding import ground_nodes
from app.services.progress import GraphProgress
from app.services.prompts import GRAPH_SYSTEM, build_graph_user

log = logging.getLogger(__name__)


def create_goal_graph(db: Session, payload: GoalCreate, user: User | None = None) -> Graph:
    answers = [{"question": a.question.strip(), "answer": a.answer.strip()} for a in payload.answers if a.question.strip()]
    goal = Goal(
        user_id=user.id if user else None,
        raw_goal=payload.goal.strip(),
        background=payload.background.strip(),
        time_budget=payload.time_budget.strip(),
        purpose=payload.purpose.strip(),
        clarifications=answers,
        attachment_ids=list(payload.attachment_ids),
    )
    db.add(goal)
    db.flush()
    graph = Graph(goal_id=goal.id, user_id=user.id if user else None, title=payload.goal.strip()[:60], status="generating", progress={"step": "plan", "done": 0, "total": 0})
    db.add(graph)
    db.commit()
    if user is not None:
        profile_service.record_event(db, user.id, "goal", f"创建学习目标：{goal.raw_goal[:100]}", "graph", graph.id, {"answers": len(answers), "attachments": len(goal.attachment_ids)})
        blob = "学习目标：" + goal.raw_goal + "\n基础：" + goal.background + "\n时间：" + goal.time_budget + "\n用途：" + goal.purpose
        if answers:
            blob += "\n澄清问答：\n" + "\n".join(f"问：{a['question']} 答：{a['answer']}" for a in answers)
        profile_service.extract_facts(user.id, blob, "clarify")
    return graph


def persist_plan(db: Session, graph: Graph, plan: LLMGraph) -> None:
    graph.title = plan.title.strip()[:200] or graph.title
    graph.summary = plan.summary.strip()
    graph.learner_profile = plan.learner_profile.strip()

    root = Node(graph_id=graph.id, ref="root", label=graph.title, description=plan.root_description.strip(), node_type="root", layer=0, order_index=0, weight=100, grounding_status="skipped")
    db.add(root)
    db.flush()

    by_ref: dict[str, Node] = {}
    last_module: Node | None = None
    order = 1
    for spec in plan.nodes:
        ref = spec.ref.strip()
        if not ref or ref in by_ref:
            ref = f"{ref or 'n'}_{order}"
        node_type = spec.node_type if spec.node_type in {"module", "concept", "practice"} else "concept"
        parent: Node
        if node_type == "module" or not spec.parent_ref:
            node_type = "module"
            parent = root
        else:
            parent = by_ref.get(spec.parent_ref.strip()) or last_module or root
            if parent.node_type not in {"module", "root"}:
                parent = last_module or root
        node = Node(
            graph_id=graph.id,
            ref=ref,
            label=spec.label.strip()[:200],
            description=spec.description.strip(),
            node_type=node_type,
            layer=1 if parent is root else 2,
            order_index=order,
            parent_id=parent.id,
            weight=50,
            difficulty=max(1, min(5, int(spec.difficulty or 2))),
            est_minutes=max(5, min(600, int(spec.est_minutes or 30))),
            teaching_strategy=spec.teaching_strategy.strip(),
            search_queries=[q.strip() for q in spec.search_queries if q and q.strip()][:3],
        )
        db.add(node)
        db.flush()
        by_ref[ref] = node
        if node_type == "module":
            last_module = node
        order += 1

    for node in by_ref.values():
        if node.parent_id:
            db.add(Edge(graph_id=graph.id, source_id=node.parent_id, target_id=node.id, relation="contains"))
    seen: set[tuple[str, str]] = set()
    for spec in plan.edges:
        src = by_ref.get(spec.source_ref.strip())
        dst = by_ref.get(spec.target_ref.strip())
        if not src or not dst or src.id == dst.id or (src.id, dst.id) in seen:
            continue
        seen.add((src.id, dst.id))
        db.add(Edge(graph_id=graph.id, source_id=src.id, target_id=dst.id, relation="prerequisite" if spec.relation == "prerequisite" else "related"))
    db.commit()


def run_pipeline(graph_id: str) -> None:
    db = session_factory()()
    try:
        graph = db.get(Graph, graph_id)
        if graph is None:
            return
        settings = get_settings()
        llm = get_llm()
        graph.provider_trace = {"llm": llm.name, "model": llm.model}
        db.commit()
        profile_ctx = profile_service.profile_context(db, graph.user_id)
        attachments_ctx = attachment_context(db, graph.user_id, graph.goal.attachment_ids or []) if graph.user_id else ""
        user_prompt = build_graph_user(graph.goal, profile_ctx, attachments_ctx)
        degraded = ""
        try:
            plan = call_with_retries(lambda: llm.structured(system=GRAPH_SYSTEM, user=user_prompt, schema=LLMGraph, effort="high", max_tokens=8000), attempts=3, label="graph-plan")
        except LLMError as exc:
            log.error("graph plan failed after retries for %s: %s", graph_id, exc)
            try:  # one more try with a lighter budget before giving up on the model
                plan = call_with_retries(lambda: llm.structured(system=GRAPH_SYSTEM, user=user_prompt + "\n\n（请精简：3 个模块、每个模块 2 个知识点。）", schema=LLMGraph, effort="low", max_tokens=5000), attempts=2, label="graph-plan-lite")
            except LLMError as exc2:
                plan = fallback_graph(graph.goal.raw_goal)
                degraded = f"{exc2}"[:300]
        graph.provider_trace = {**(graph.provider_trace or {}), "degraded": bool(degraded), "degraded_reason": degraded}
        persist_plan(db, graph, plan)
        db.refresh(graph)
        progress = GraphProgress(graph)
        learnable = progress.learnable_nodes()
        for node in graph.nodes:
            if node.node_type == "root" or (node.node_type == "module" and progress.children.get(node.id)):
                node.grounding_status = "skipped"
        graph.status = "grounding"
        graph.progress = {"step": "search", "done": 0, "total": len(learnable) * 2}
        db.commit()

        def report(step: str, done: int, total: int) -> None:
            graph.progress = {"step": step, "done": done, "total": total}
            db.commit()

        ground_nodes(db, learnable, get_search(), get_reader(), settings, report)
        graph.status = "ready"
        graph.progress = {"step": "ready", "done": 1, "total": 1}
        db.commit()
    except Exception:  # pragma: no cover - defensive
        log.exception("pipeline failed for %s", graph_id)
        db.rollback()
        graph = db.get(Graph, graph_id)
        if graph is not None:
            graph.status = "failed"
            graph.error = traceback.format_exc()[-1500:]
            db.commit()
    finally:
        db.close()


def start_pipeline(graph_id: str) -> None:
    threading.Thread(target=run_pipeline, args=(graph_id,), name=f"pipeline-{graph_id}", daemon=True).start()


def reground_node(db: Session, node: Node) -> int:
    counts = ground_nodes(db, [node], get_search(), get_reader(), get_settings())
    return counts.get(node.id, 0)
