"""Deterministic offline provider: lets the whole product run (and the test-suite pass) without any API key."""
from __future__ import annotations

import re
import time
from collections.abc import Iterator
from typing import TypeVar

from pydantic import BaseModel

from app.schemas import LLMCard, LLMCards, LLMGrade, LLMGraph, LLMGraphEdge, LLMGraphNode, LLMQuiz, LLMQuizQuestion

T = TypeVar("T", bound=BaseModel)


def _topic_from_prompt(user: str) -> str:
    m = re.search(r"学习目标[:：]\s*(.+)", user)
    topic = (m.group(1) if m else user).strip().splitlines()[0]
    topic = re.sub(r"^.*?背后的知识[:：]\s*", "", topic)
    topic = re.sub(r"^(我想|我要|想要|希望|帮我|请)?(在.*?内)?(系统)?(学习|学会|搞懂|理解|掌握|了解|入门|复习)?", "", topic).strip(" ，。,.:：")
    topic = re.split(r"[，,、；;。！？!?]|(?:\s+(?:能|并|然后|以便|用来|来|为了))", topic)[0].strip()
    topic = re.sub(r"(是怎么回事|的知识|背后的知识)$", "", topic).strip()
    return topic[:30] or "新主题"


def _mock_graph(user: str) -> LLMGraph:
    topic = _topic_from_prompt(user)
    modules = [("m1", f"{topic}的基本概念", "先建立整体图景与核心术语"), ("m2", f"{topic}的核心原理", "理解内部机制与关键推导"), ("m3", f"{topic}的应用与实践", "在真实问题中运用并形成判断")]
    concepts = {
        "m1": [f"{topic}是什么", f"{topic}要解决的问题", f"{topic}的发展脉络"],
        "m2": [f"{topic}的核心机制", f"{topic}的关键公式或流程", f"{topic}的常见误区"],
        "m3": [f"{topic}的典型应用", f"动手实践：一个{topic}小项目"],
    }
    nodes: list[LLMGraphNode] = []
    edges: list[LLMGraphEdge] = []
    for i, (ref, label, desc) in enumerate(modules):
        nodes.append(LLMGraphNode(ref=ref, label=label, description=desc, node_type="module", parent_ref=None, difficulty=i + 1, est_minutes=60, teaching_strategy="先给出百科式定义，再用一个生活化例子建立直觉。", search_queries=[label]))
        if i > 0:
            edges.append(LLMGraphEdge(source_ref=modules[i - 1][0], target_ref=ref, relation="prerequisite"))
        prev = None
        for j, clabel in enumerate(concepts[ref]):
            cref = f"{ref}c{j + 1}"
            ntype = "practice" if clabel.startswith("动手实践") else "concept"
            nodes.append(LLMGraphNode(ref=cref, label=clabel, description=f"围绕「{clabel}」的关键知识点，是理解{label}的基础。", node_type=ntype, parent_ref=ref, difficulty=min(5, i + j + 1), est_minutes=25, teaching_strategy="定义→例子→误区→自检。", search_queries=[clabel, f"{topic} {clabel}"]))
            if prev:
                edges.append(LLMGraphEdge(source_ref=prev, target_ref=cref, relation="prerequisite"))
            prev = cref
    return LLMGraph(
        title=topic,
        summary=f"这条路线把「{topic}」拆成基本概念、核心原理和应用实践三个模块，先建立整体图景，再深入机制，最后在实践中巩固。每个知识点都关联了知乎上的高赞讨论作为学习材料。",
        learner_profile="（离线演示模式）默认按零基础、每天 1 小时的节奏设计。",
        root_description=f"「{topic}」的整体知识地图。",
        nodes=nodes,
        edges=edges,
    )


def _mock_quiz(user: str) -> LLMQuiz:
    label = re.search(r"知识点[:：]\s*(.+)", user)
    topic = (label.group(1) if label else "该知识点").strip().splitlines()[0]
    return LLMQuiz(
        questions=[
            LLMQuizQuestion(qtype="single", stem=f"关于「{topic}」，下列说法最准确的是？", options=["它只是一个孤立的名词，与其他知识无关", "它有明确的定义，并与前后知识点存在依赖关系", "它无法被验证或练习", "它只在考试中出现"], answer_index=1, explanation="知识点在图谱中通过前置关系相互连接，理解定义与依赖关系是掌握的第一步。", source_index=1),
            LLMQuizQuestion(qtype="single", stem=f"学习「{topic}」时最容易出现的误区是？", options=["只背定义不看例子", "先看例子再回到定义", "用自己的话复述", "做一个小练习验证"], answer_index=0, explanation="只背定义而不结合例子，是知乎高赞回答中反复提到的常见误区。", source_index=1),
            LLMQuizQuestion(qtype="single", stem=f"下列哪一项最能说明你已经掌握了「{topic}」？", options=["能背出术语", "能用自己的话向初学者解释并举例", "读过一篇文章", "收藏了多个回答"], answer_index=1, explanation="费曼学习法：能教会别人，才算真正理解。", source_index=0),
            LLMQuizQuestion(qtype="feynman", stem=f"请用 3-5 句话，向一位完全不了解的朋友解释「{topic}」是什么、为什么重要。", options=[], answer_index=-1, explanation="从定义、例子和用途三方面组织你的解释。", source_index=0),
        ]
    )


def _mock_grade(user: str) -> LLMGrade:
    answer = user.split("学习者的回答", 1)[-1]
    n = len(answer.strip())
    score = max(35, min(96, 40 + n // 3))
    return LLMGrade(score=score, feedback="（离线演示评分）你的解释抓住了主线。若能补充一个具体例子，并说明它与前置知识点的关系，会更完整。", strengths=["表达清晰，有主线"], gaps=["缺少具体例子", "没有说明与其他知识点的关系"])


def _mock_cards(user: str) -> LLMCards:
    label = re.search(r"知识点[:：]\s*(.+)", user)
    topic = (label.group(1) if label else "该知识点").strip().splitlines()[0]
    return LLMCards(cards=[
        LLMCard(front=f"{topic} 的一句话定义是？", back=f"（离线演示）{topic} 是本模块的核心概念，需要结合例子理解。", source_index=1),
        LLMCard(front=f"学习 {topic} 最常见的误区？", back="只背定义不结合例子，缺少动手验证。", source_index=1),
        LLMCard(front=f"如何自检是否掌握了 {topic}？", back="能用自己的话向初学者解释，并举出一个应用场景。", source_index=0),
    ])


class MockProvider:
    name = "mock"
    model = "offline-demo"

    def __init__(self, delay: float = 0.0) -> None:
        self.delay = delay

    def structured(self, *, system: str, user: str, schema: type[T], effort: str = "medium", max_tokens: int = 8000) -> T:
        if schema is LLMGraph:
            return _mock_graph(user)  # type: ignore[return-value]
        if schema is LLMQuiz:
            return _mock_quiz(user)  # type: ignore[return-value]
        if schema is LLMGrade:
            return _mock_grade(user)  # type: ignore[return-value]
        if schema is LLMCards:
            return _mock_cards(user)  # type: ignore[return-value]
        raise NotImplementedError(f"MockProvider has no canned output for {schema.__name__}")

    def complete(self, *, system: str, user: str, max_tokens: int = 4000) -> str:
        return "".join(self.stream(system=system, messages=[{"role": "user", "content": user}], max_tokens=max_tokens))

    def stream(self, *, system: str, messages: list[dict[str, str]], max_tokens: int = 6000) -> Iterator[str]:
        user = messages[-1]["content"] if messages else ""
        label = re.search(r"知识点[:：]\s*(.+)", user)
        topic = (label.group(1) if label else "这个知识点").strip().splitlines()[0]
        if "学习者提问" in user:
            q = user.split("学习者提问", 1)[-1].strip(" ：:\n")
            text = f"（离线演示模式）关于「{q[:60]}」：这属于「{topic}」的延伸问题。可以先回到它的定义，再看知乎来源 [1] 中给出的例子，最后用自己的话复述一遍。"
        else:
            text = (
                f"## 一句话定义\n\n**{topic}** 是这个模块中的核心知识点。用一句话说，它回答的是「为什么需要它、它如何工作」这两个问题 [1]。\n\n"
                f"## 直觉理解\n\n把它想象成一个熟悉的生活场景：先有一个需要解决的问题，再有一个逐步逼近答案的方法。知乎上的高赞回答通常从这个角度切入 [1][2]。\n\n"
                f"## 关键要点\n\n1. 明确定义，区分它和相邻概念的边界。\n2. 掌握核心机制，知道输入是什么、输出是什么。\n3. 至少能举一个真实应用的例子 [2]。\n\n"
                f"## 常见误区\n\n- 只记住术语，不理解动机。\n- 把特例当成一般规律。\n\n"
                f"## 知乎观点对照\n\n不同回答者的侧重点不同：有人强调直觉 [1]，有人强调形式化推导 [2]。初学者建议先建立直觉再补推导。\n\n"
                f"## 掌握自检\n\n- 你能用自己的话解释它是什么吗？\n- 你能举一个例子说明它解决了什么问题吗？\n\n> 这是离线演示内容。配置 LLM 后，讲解会真正基于右侧的知乎来源生成并逐句引用。"
            )
        for i in range(0, len(text), 24):
            if self.delay:
                time.sleep(self.delay)
            yield text[i : i + 24]
