"""学习者档案 (learner profile): facts + interaction timeline, written by every interaction and used by every prompt."""
from __future__ import annotations

import logging
import re
import threading
from typing import Any

from sqlalchemy.orm import Session

from app.db import session_factory
from app.llm.base import LLMError
from app.models import Attachment, Goal, Graph, ProfileEvent, ProfileFact, User, utcnow
from app.schemas import LLMProfileFacts

log = logging.getLogger(__name__)

KIND_LABELS = {"background": "背景", "skill": "已掌握", "goal": "目标", "preference": "偏好", "interest": "兴趣", "progress": "进度", "other": "其他"}
ASYNC_EXTRACTION = True  # tests flip this to run extraction inline

PROFILE_EXTRACT_SYSTEM = """你是「知径 LearnPath」的学习档案管理员。从学习者的一段话或一次行为中，提取值得长期记住、能影响后续学习路线设计的事实。

规则：
- 只提取明确表达或可稳妥推断的事实：专业/身份、已掌握的知识与工具（尽量具体到程度）、学习目标与动机、偏好的学习方式、兴趣、时间约束。
- 每条一句话，第三人称，不带评价；kind 取 background/skill/goal/preference/interest/progress/other。
- 没有新信息就返回空列表；不要把题目内容、通用常识或平台功能当作事实。最多 5 条。"""


def _norm(text: str) -> str:
    return re.sub(r"[\s，。,.；;：:！!？?]", "", text).lower()


def record_event(db: Session, user_id: str | None, kind: str, summary: str, ref_type: str = "", ref_id: str = "", detail: dict[str, Any] | None = None) -> ProfileEvent | None:
    if not user_id:
        return None
    event = ProfileEvent(user_id=user_id, kind=kind, summary=summary[:500], ref_type=ref_type, ref_id=ref_id, detail=detail or {})
    db.add(event)
    db.commit()
    return event


def add_fact(db: Session, user_id: str | None, kind: str, text: str, source: str, confidence: float = 0.8) -> ProfileFact | None:
    text = " ".join(text.split()).strip()
    if not user_id or len(text) < 2:
        return None
    kind = kind if kind in KIND_LABELS else "other"
    key = _norm(text)
    for existing in db.query(ProfileFact).filter(ProfileFact.user_id == user_id).all():
        if _norm(existing.text) == key:
            existing.confidence = max(existing.confidence, confidence)
            existing.updated_at = utcnow()
            db.commit()
            return existing
    fact = ProfileFact(user_id=user_id, kind=kind, text=text[:500], source=source, confidence=max(0.0, min(1.0, confidence)))
    db.add(fact)
    db.commit()
    return fact


def list_facts(db: Session, user_id: str) -> list[ProfileFact]:
    order = {k: i for i, k in enumerate(KIND_LABELS)}
    facts = db.query(ProfileFact).filter(ProfileFact.user_id == user_id).all()
    return sorted(facts, key=lambda f: (order.get(f.kind, 99), -f.confidence, f.created_at))


def profile_context(db: Session, user_id: str | None, limit: int = 14) -> str:
    """Compact profile block for prompts (empty string when nothing is known)."""
    if not user_id:
        return ""
    facts = [f for f in list_facts(db, user_id) if f.kind != "progress"][:limit]
    progress = [f for f in list_facts(db, user_id) if f.kind == "progress"][-4:]
    lines = [f"- [{KIND_LABELS.get(f.kind, '其他')}] {f.text}" for f in facts + progress]
    return "\n".join(lines)


def _extract(user_id: str, text: str, source: str, context: str) -> None:
    from app.llm.factory import get_llm

    db = session_factory()()
    try:
        llm = get_llm()
        known = profile_context(db, user_id)
        user = f"来源：{source}\n{('相关上下文：' + context + chr(10)) if context else ''}内容：\n{text[:3000]}\n\n已记录的档案（避免重复）：\n{known or '（空）'}"
        result: LLMProfileFacts = llm.structured(system=PROFILE_EXTRACT_SYSTEM, user=user, schema=LLMProfileFacts, effort="low", max_tokens=1500)
        for fact in result.facts[:5]:
            add_fact(db, user_id, fact.kind, fact.text, source, fact.confidence)
    except LLMError as exc:
        log.info("profile extraction skipped: %s", exc)
    except Exception:  # pragma: no cover - background safety net
        log.exception("profile extraction failed")
    finally:
        db.close()


def extract_facts(user_id: str | None, text: str, source: str, context: str = "") -> None:
    """Run LLM fact extraction (in a background thread by default) over a piece of learner input."""
    if not user_id or len(text.strip()) < 6:
        return
    if ASYNC_EXTRACTION:
        threading.Thread(target=_extract, args=(user_id, text, source, context), daemon=True).start()
    else:
        _extract(user_id, text, source, context)


def merge_guest(db: Session, guest: User, user: User) -> None:
    """Move everything a guest created onto the freshly logged-in account, then drop the guest."""
    if guest.id == user.id:
        return
    for model in (Goal, Graph, ProfileFact, ProfileEvent, Attachment):
        db.query(model).filter(model.user_id == guest.id).update({"user_id": user.id}, synchronize_session=False)
    db.delete(guest)
    db.commit()


def user_stats(db: Session, user_id: str) -> dict[str, Any]:
    from app.services.progress import GraphProgress

    graphs = db.query(Graph).filter(Graph.user_id == user_id).all()
    learnable = mastered = started = minutes = 0
    for graph in graphs:
        if graph.status != "ready":
            continue
        stats = GraphProgress(graph).stats()
        learnable += stats.learnable_nodes
        mastered += stats.mastered_nodes
        started += stats.started_nodes
        minutes += stats.minutes_total - stats.minutes_remaining
    events = db.query(ProfileEvent).filter(ProfileEvent.user_id == user_id).count()
    facts = db.query(ProfileFact).filter(ProfileFact.user_id == user_id).count()
    return {"graphs": len(graphs), "learnable_nodes": learnable, "mastered_nodes": mastered, "started_nodes": started, "minutes_learned": minutes, "events": events, "facts": facts}
