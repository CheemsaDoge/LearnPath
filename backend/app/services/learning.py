"""Learning interactions on a node: lesson, quiz, cards, chat, export."""
from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.llm.base import LLMError, LLMProvider
from app.models import CardDeck, ChatMessage, Evidence, Graph, Lesson, Node, Quiz, utcnow
from app.schemas import LLMCards, LLMGrade, LLMQuiz, NextAction, QuestionResult, QuizResultOut
from app.services.grounding import source_context
from app.services.progress import GraphProgress, update_mastery
from app.services.prompts import (
    CARDS_SYSTEM,
    GRADE_SYSTEM,
    LESSON_SYSTEM,
    QUIZ_SYSTEM,
    build_cards_user,
    build_chat_system,
    build_grade_user,
    build_lesson_user,
    build_quiz_user,
)

MAX_CHAT_HISTORY = 12


class LearningService:
    def __init__(self, db: Session, llm: LLMProvider) -> None:
        self.db = db
        self.llm = llm

    # ------------------------------------------------------------------ context
    def _ctx(self, node: Node) -> dict[str, Any]:
        graph = node.graph
        parent = self.db.get(Node, node.parent_id) if node.parent_id else None
        context, citations = source_context(node)
        return {
            "parent_label": parent.label if parent and parent.node_type != "root" else "",
            "learner_profile": graph.learner_profile,
            "goal_text": graph.goal.raw_goal,
            "context": context,
            "citations": citations,
        }

    # ------------------------------------------------------------------ lesson
    def latest_lesson(self, node: Node) -> Lesson | None:
        return max(node.lessons, key=lambda l: l.created_at) if node.lessons else None

    def stream_lesson(self, node: Node) -> Iterator[dict[str, Any]]:
        ctx = self._ctx(node)
        yield {"citations": ctx["citations"]}
        chunks: list[str] = []
        for delta in self.llm.stream(
            system=LESSON_SYSTEM,
            messages=[{"role": "user", "content": build_lesson_user(node, ctx["parent_label"], ctx["learner_profile"], ctx["goal_text"], ctx["context"])}],
            max_tokens=6000,
        ):
            chunks.append(delta)
            yield {"delta": delta}
        content = "".join(chunks).strip()
        for old in list(node.lessons):
            self.db.delete(old)
        lesson = Lesson(node_id=node.id, content_md=content, citations=ctx["citations"])
        self.db.add(lesson)
        node.last_studied_at = utcnow()
        self.db.add(Evidence(node_id=node.id, kind="lesson", score=0.0, detail={"chars": len(content), "sources": len(ctx["citations"])}))
        self.db.commit()
        yield {"done": True, "lesson_id": lesson.id}

    # ------------------------------------------------------------------ quiz
    def generate_quiz(self, node: Node) -> Quiz:
        ctx = self._ctx(node)
        plan: LLMQuiz = self.llm.structured(
            system=QUIZ_SYSTEM,
            user=build_quiz_user(node, ctx["parent_label"], ctx["learner_profile"], ctx["goal_text"], ctx["context"]),
            schema=LLMQuiz,
            effort="medium",
            max_tokens=6000,
        )
        questions: list[dict[str, Any]] = []
        for i, q in enumerate(plan.questions[:6], start=1):
            qtype = "feynman" if q.qtype == "feynman" or not q.options else "single"
            options = [o.strip() for o in q.options][:4] if qtype == "single" else []
            if qtype == "single" and len(options) < 2:
                continue
            answer_index = q.answer_index if qtype == "single" and 0 <= q.answer_index < len(options) else (-1 if qtype == "feynman" else 0)
            questions.append(
                {
                    "id": f"q{i}",
                    "qtype": qtype,
                    "stem": q.stem.strip(),
                    "options": options,
                    "answer_index": answer_index,
                    "explanation": q.explanation.strip(),
                    "source_index": int(q.source_index or 0),
                }
            )
        if not any(q["qtype"] == "feynman" for q in questions):
            questions.append({"id": f"q{len(questions) + 1}", "qtype": "feynman", "stem": f"请用自己的话向一位初学者解释「{node.label}」：它是什么、为什么重要、举一个例子。", "options": [], "answer_index": -1, "explanation": "从定义、例子和用途三方面组织你的解释。", "source_index": 0})
        quiz = Quiz(node_id=node.id, questions=questions)
        self.db.add(quiz)
        self.db.commit()
        return quiz

    def grade_quiz(self, quiz: Quiz, answers: dict[str, Any]) -> QuizResultOut:
        node = self.db.get(Node, quiz.node_id)
        assert node is not None
        ctx = self._ctx(node)
        results: list[QuestionResult] = []
        weighted_sum = 0.0
        weight_total = 0.0
        for q in quiz.questions:
            given = answers.get(q["id"])
            if q["qtype"] == "single":
                try:
                    chosen = int(given) if given is not None and given != "" else None
                except (TypeError, ValueError):
                    chosen = None
                correct = chosen is not None and chosen == q["answer_index"]
                score = 100 if correct else 0
                results.append(QuestionResult(id=q["id"], qtype="single", correct=correct, score=score, your_answer=chosen, answer_index=q["answer_index"], explanation=q["explanation"]))
                weighted_sum += score
                weight_total += 1
            else:
                text = (given or "").strip() if isinstance(given, str) else ""
                if not text:
                    results.append(QuestionResult(id=q["id"], qtype="feynman", correct=None, score=0, your_answer="", answer_index=None, explanation=q["explanation"], feedback="未作答。用自己的话解释一遍，是检验理解最有效的方式。"))
                    weighted_sum += 0
                    weight_total += 2
                    continue
                try:
                    grade: LLMGrade = self.llm.structured(system=GRADE_SYSTEM, user=build_grade_user(node, q["stem"], text, ctx["context"]), schema=LLMGrade, effort="low", max_tokens=2000)
                    score = max(0, min(100, int(grade.score)))
                    feedback = grade.feedback.strip()
                    if grade.strengths or grade.gaps:
                        feedback += "\n\n做得好：" + "；".join(grade.strengths) if grade.strengths else ""
                        feedback += "\n\n可补充：" + "；".join(grade.gaps) if grade.gaps else ""
                except LLMError as exc:
                    score = 50
                    feedback = f"（自动评分暂不可用：{exc}）已按 50 分记录。"
                results.append(QuestionResult(id=q["id"], qtype="feynman", correct=None, score=score, your_answer=text, answer_index=None, explanation=q["explanation"], feedback=feedback))
                weighted_sum += score * 2
                weight_total += 2
        total = int(round(weighted_sum / weight_total)) if weight_total else 0
        stars_before = node.mastery_stars
        update_mastery(node, total)
        quiz.submitted = True
        quiz.result = {"score": total, "results": [r.model_dump() for r in results]}
        self.db.add(Evidence(node_id=node.id, kind="quiz", score=float(total), detail={"quiz_id": quiz.id, "questions": len(results), "correct_single": sum(1 for r in results if r.correct)}))
        self.db.commit()
        self.db.refresh(node.graph)
        progress = GraphProgress(node.graph)
        star_text = "★" * node.mastery_stars + "☆" * (3 - node.mastery_stars)
        if node.mastery_stars > stars_before:
            summary = f"本次 {total} 分，掌握度升到 {star_text}。"
        elif node.mastery_stars == 3:
            summary = f"本次 {total} 分，继续保持 {star_text}。"
        else:
            summary = f"本次 {total} 分，掌握度 {star_text}。看看解析，再来一次。"
        return QuizResultOut(
            quiz_id=quiz.id,
            node_id=node.id,
            score=total,
            results=results,
            mastery_score=node.mastery_score,
            mastery_stars=node.mastery_stars,
            stars_before=stars_before,
            next_actions=progress.next_actions(),
            summary=summary,
        )

    # ------------------------------------------------------------------ cards
    def latest_cards(self, node: Node) -> CardDeck | None:
        decks = self.db.query(CardDeck).filter(CardDeck.node_id == node.id).order_by(CardDeck.created_at.desc()).all()
        return decks[0] if decks else None

    def generate_cards(self, node: Node) -> CardDeck:
        ctx = self._ctx(node)
        plan: LLMCards = self.llm.structured(
            system=CARDS_SYSTEM,
            user=build_cards_user(node, ctx["parent_label"], ctx["learner_profile"], ctx["goal_text"], ctx["context"]),
            schema=LLMCards,
            effort="low",
            max_tokens=4000,
        )
        cards = [{"front": c.front.strip(), "back": c.back.strip(), "source_index": int(c.source_index or 0)} for c in plan.cards[:10] if c.front.strip()]
        deck = CardDeck(node_id=node.id, cards=cards)
        self.db.add(deck)
        self.db.commit()
        return deck

    # ------------------------------------------------------------------ chat
    def stream_chat(self, node: Node, question: str) -> Iterator[dict[str, Any]]:
        ctx = self._ctx(node)
        history = self.db.query(ChatMessage).filter(ChatMessage.node_id == node.id).order_by(ChatMessage.created_at.asc()).all()[-MAX_CHAT_HISTORY:]
        messages = [{"role": m.role, "content": m.content} for m in history]
        if messages and messages[0]["role"] != "user":
            messages = messages[1:]
        messages.append({"role": "user", "content": f"学习者提问：{question.strip()}"})
        user_msg = ChatMessage(node_id=node.id, role="user", content=question.strip())
        self.db.add(user_msg)
        self.db.commit()
        yield {"citations": ctx["citations"], "message_id": user_msg.id}
        chunks: list[str] = []
        for delta in self.llm.stream(
            system=build_chat_system(node, ctx["parent_label"], ctx["learner_profile"], ctx["goal_text"], ctx["context"]),
            messages=messages,
            max_tokens=2500,
        ):
            chunks.append(delta)
            yield {"delta": delta}
        answer = "".join(chunks).strip()
        reply = ChatMessage(node_id=node.id, role="assistant", content=answer)
        self.db.add(reply)
        self.db.add(Evidence(node_id=node.id, kind="chat", score=0.0, detail={"question": question.strip()[:200]}))
        self.db.commit()
        yield {"done": True, "message_id": reply.id}


# ---------------------------------------------------------------------- export
def export_markdown(graph: Graph) -> str:
    progress = GraphProgress(graph)
    stats = progress.stats()
    lines = [f"# {graph.title} · 学习路径", "", f"> 学习目标：{graph.goal.raw_goal}", ""]
    if graph.learner_profile:
        lines += [f"> 学习者画像：{graph.learner_profile}", ""]
    if graph.summary:
        lines += [graph.summary, ""]
    lines += [f"进度：{stats.mastered_nodes}/{stats.learnable_nodes} 个知识点已掌握（≥2 星），预计剩余 {stats.minutes_remaining} 分钟。", ""]
    modules = progress.children.get(next((n.id for n in graph.nodes if n.node_type == "root"), None), [])
    for module in modules:
        lines.append(f"## {module.label}")
        if module.description:
            lines.append(module.description)
        lines.append("")
        kids = progress.children.get(module.id, []) or [module]
        for node in kids:
            if node is module and progress.children.get(module.id):
                continue
            stars = "★" * node.mastery_stars + "☆" * (3 - node.mastery_stars)
            tag = "练习" if node.node_type == "practice" else "知识点"
            lines.append(f"### {node.label}  `{tag}` {stars} · 约 {node.est_minutes} 分钟")
            if node.description:
                lines.append(node.description)
            if node.sources:
                lines.append("")
                lines.append("知乎来源：")
                for link in node.sources:
                    s = link.source
                    lines.append(f"- [{s.title or s.url}]({s.url})")
            lesson = max(node.lessons, key=lambda l: l.created_at) if node.lessons else None
            if lesson:
                lines += ["", "<details><summary>讲解</summary>", "", lesson.content_md, "", "</details>"]
            lines.append("")
    lines += ["---", f"由 知径 LearnWay 生成 · {datetime.now().strftime('%Y-%m-%d %H:%M')}", ""]
    return "\n".join(lines)


def next_actions_for(graph: Graph) -> list[NextAction]:
    return GraphProgress(graph).next_actions()


def evidence_payload(node: Node) -> list[dict[str, Any]]:
    return [{"id": e.id, "kind": e.kind, "score": e.score, "detail": e.detail, "created_at": e.created_at.isoformat()} for e in sorted(node.evidence, key=lambda e: e.created_at, reverse=True)]


def dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)
