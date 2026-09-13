"""Deterministic fallback content used when the model is unavailable after retries.

Everything here is built only from data we already have (sources, node metadata), so it never fails and never
misleads: each fallback says explicitly that it is a temporary substitute.
"""
from __future__ import annotations

from typing import Any

from app.llm.mock_provider import MockProvider
from app.models import Node
from app.schemas import LLMCards, LLMClarification, LLMGrade, LLMGraph, LLMQuiz

DEGRADED_NOTE = "> ⚠️ AI 服务暂时波动，这是根据知乎来源自动整理的临时版本。稍后点击「重新生成」即可获得完整讲解。"
_mock = MockProvider()


def fallback_lesson(node: Node, context: str, citations: list[dict[str, Any]]) -> str:
    parts = [f"## {node.label}", "", DEGRADED_NOTE, ""]
    if node.description:
        parts += ["## 一句话定义", "", node.description, ""]
    if citations:
        parts += ["## 知乎来源摘要", ""]
        for link, cite in zip(node.sources, citations):
            body = (link.source.content or link.source.snippet or "").strip().replace("\n", " ")
            if body:
                parts.append(f"- **{cite['title']}**：{body[:220]}… [{cite['index']}]")
        parts.append("")
    if node.teaching_strategy:
        parts += ["## 学习建议", "", node.teaching_strategy, ""]
    parts += ["## 掌握自检", "", f"- 你能用自己的话说清「{node.label}」是什么、解决什么问题吗？", "- 你能举一个具体例子吗？"]
    return "\n".join(parts)


def fallback_quiz(node: Node) -> LLMQuiz:
    return _mock.structured(system="", user=f"知识点：{node.label}", schema=LLMQuiz)


def fallback_cards(node: Node) -> LLMCards:
    return _mock.structured(system="", user=f"知识点：{node.label}", schema=LLMCards)


def fallback_grade(answer: str) -> LLMGrade:
    n = len(answer.strip())
    score = 30 if n < 20 else 55 if n < 80 else 70
    return LLMGrade(score=score, feedback="AI 评分暂时不可用，已按回答的完整度给出临时分数；稍后可以再次提交获得详细反馈。", strengths=["完成了费曼解释"], gaps=["等待 AI 详细评审"])


def fallback_clarify(goal: str) -> LLMClarification:
    return _mock.structured(system="", user=f"学习目标：{goal}", schema=LLMClarification)


def fallback_graph(goal_text: str) -> LLMGraph:
    plan: LLMGraph = _mock.structured(system="", user=f"学习目标：{goal_text}", schema=LLMGraph)
    plan.summary = "AI 服务暂时波动，这是自动生成的基础路线骨架；知乎来源仍是真实检索结果。稍后可在图谱页点击「重新生成」获得完整个性化路线。"
    plan.learner_profile = ""
    return plan
