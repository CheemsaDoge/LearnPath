"""Pydantic schemas: API contracts + structured-output models for the LLM."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# --------------------------------------------------------------------------- #
# LLM structured outputs (kept free of exotic JSON-schema constraints so that
# Anthropic structured outputs / OpenAI json mode both accept them)
# --------------------------------------------------------------------------- #
class LLMGraphNode(BaseModel):
    ref: str = Field(description="短且唯一的引用标识，例如 m1、c3")
    label: str = Field(description="知识点名称，聚焦知识本体，不带“学习/掌握”等套话")
    description: str = Field(description="2-3 句说明：这个知识点是什么、为什么对目标重要")
    node_type: Literal["module", "concept", "practice"]
    parent_ref: str | None = Field(description="module 填 null；concept/practice 填所属 module 的 ref")
    difficulty: int = Field(description="1-5，1 最容易")
    est_minutes: int = Field(description="预计学习分钟数")
    teaching_strategy: str = Field(description="针对该知识点的讲解策略：切入方式、关键例子、常见误区、可验证的掌握标准")
    search_queries: list[str] = Field(description="1-3 个用于在知乎检索优质内容的中文搜索词")


class LLMGraphEdge(BaseModel):
    source_ref: str
    target_ref: str
    relation: Literal["prerequisite", "related"]


class LLMGraph(BaseModel):
    title: str = Field(description="图谱标题：简洁的学科/主题名")
    summary: str = Field(description="给学习者的 3-5 句路线总览")
    learner_profile: str = Field(description="对学习者起点、目标与时间约束的一句话画像")
    root_description: str = Field(description="根节点（主题）的一句话定义")
    nodes: list[LLMGraphNode]
    edges: list[LLMGraphEdge]


class LLMQuizQuestion(BaseModel):
    qtype: Literal["single", "feynman"]
    stem: str
    options: list[str] = Field(description="single 题给 4 个选项；feynman 题给空列表")
    answer_index: int = Field(description="single 题正确选项下标(0-3)；feynman 题填 -1")
    explanation: str = Field(description="答案解析，尽量引用知乎来源观点")
    source_index: int = Field(description="依据的来源编号（从 1 开始），没有则 0")


class LLMQuiz(BaseModel):
    questions: list[LLMQuizQuestion]


class LLMGrade(BaseModel):
    score: int = Field(description="0-100")
    feedback: str = Field(description="面向学习者的反馈，先肯定再指出缺口，最后给一句改进建议")
    strengths: list[str]
    gaps: list[str]


class LLMCard(BaseModel):
    front: str = Field(description="卡片正面：一个问题或术语")
    back: str = Field(description="卡片背面：简洁准确的答案")
    source_index: int = Field(description="依据的来源编号（从 1 开始），没有则 0")


class LLMCards(BaseModel):
    cards: list[LLMCard]


class LLMClarifyQuestion(BaseModel):
    id: str = Field(description="q1、q2 …")
    question: str = Field(description="一句话问题，面向学习者")
    options: list[str] = Field(description="2-5 个可直接点选的简短选项；最后不要包含“其他”，界面会自带自由输入")
    multiple: bool = Field(description="是否可多选")
    why: str = Field(description="为什么这个信息会影响路线设计，一句话")


class LLMClarification(BaseModel):
    intro: str = Field(description="一句话复述你对目标的理解")
    questions: list[LLMClarifyQuestion] = Field(description="2-4 个问题，按重要性排序")


class LLMProfileFact(BaseModel):
    kind: Literal["background", "skill", "goal", "preference", "interest", "progress", "other"]
    text: str = Field(description="一句话事实，第三人称，例如：计算机专业大三学生；会 Java，做过 Spring Boot 项目")
    confidence: float = Field(description="0-1")


class LLMProfileFacts(BaseModel):
    facts: list[LLMProfileFact]


# --------------------------------------------------------------------------- #
# API contracts
# --------------------------------------------------------------------------- #
class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ClarifyAnswer(BaseModel):
    question: str = Field(max_length=500)
    answer: str = Field(default="", max_length=2000)


class GoalCreate(BaseModel):
    goal: str = Field(min_length=2, max_length=2000)
    background: str = Field(default="", max_length=64)
    time_budget: str = Field(default="", max_length=64)
    purpose: str = Field(default="", max_length=500)
    answers: list[ClarifyAnswer] = Field(default_factory=list)
    attachment_ids: list[str] = Field(default_factory=list)


class ClarifyRequest(BaseModel):
    goal: str = Field(min_length=2, max_length=2000)
    background: str = Field(default="", max_length=64)
    time_budget: str = Field(default="", max_length=64)
    purpose: str = Field(default="", max_length=500)
    attachment_ids: list[str] = Field(default_factory=list)


class ClarifyQuestionOut(BaseModel):
    id: str
    question: str
    options: list[str]
    multiple: bool
    why: str = ""


class ClarifyOut(BaseModel):
    intro: str
    questions: list[ClarifyQuestionOut]
    profile_hint: str = ""


class ProfileFactOut(ORMModel):
    id: str
    kind: str
    text: str
    source: str
    confidence: float
    created_at: datetime


class ProfileFactCreate(BaseModel):
    kind: Literal["background", "skill", "goal", "preference", "interest", "progress", "other"] = "other"
    text: str = Field(min_length=1, max_length=500)


class ProfileEventOut(ORMModel):
    id: str
    kind: str
    summary: str
    ref_type: str
    ref_id: str
    detail: dict[str, Any]
    created_at: datetime


class AttachmentOut(ORMModel):
    id: str
    graph_id: str | None
    filename: str
    content_type: str
    size: int
    has_text: bool = False
    summary: str = ""
    created_at: datetime


class MeOut(BaseModel):
    id: str
    name: str
    avatar: str
    headline: str
    provider: str
    is_guest: bool
    created_at: datetime


class DashboardOut(BaseModel):
    user: MeOut
    facts: list[ProfileFactOut]
    events: list[ProfileEventOut]
    graphs: list["GraphOut"]
    attachments: list[AttachmentOut]
    stats: dict[str, Any]


class SourceOut(ORMModel):
    id: str
    url: str
    kind: str
    title: str
    snippet: str
    author: str = ""
    votes: int = 0
    origin: str = "web"
    has_content: bool = False


class NodeOut(ORMModel):
    id: str
    graph_id: str
    label: str
    description: str
    node_type: str
    layer: int
    order_index: int
    parent_id: str | None
    weight: int
    difficulty: int
    est_minutes: int
    grounding_status: str
    mastery_score: float
    mastery_stars: int
    attempts: int
    source_count: int = 0
    unlocked: bool = True


class EdgeOut(ORMModel):
    id: str
    source_id: str
    target_id: str
    relation: str


class NextAction(BaseModel):
    node_id: str
    label: str
    reason: str
    est_minutes: int


class GraphStats(BaseModel):
    total_nodes: int
    learnable_nodes: int
    mastered_nodes: int
    started_nodes: int
    minutes_total: int
    minutes_remaining: int
    completion: float


class GraphOut(ORMModel):
    id: str
    goal_id: str
    user_id: str | None = None
    title: str
    summary: str
    learner_profile: str
    status: str
    error: str = ""
    progress: dict[str, Any] = {}
    degraded: bool = False
    created_at: datetime
    goal_text: str = ""
    nodes: list[NodeOut] = []
    edges: list[EdgeOut] = []
    stats: GraphStats | None = None
    next_actions: list[NextAction] = []


class GraphCreated(BaseModel):
    graph_id: str
    goal_id: str
    status: str


class EvidenceOut(ORMModel):
    id: str
    kind: str
    score: float
    detail: dict[str, Any]
    created_at: datetime


class LessonOut(ORMModel):
    id: str
    content_md: str
    citations: list[dict[str, Any]]
    created_at: datetime


class ChatMessageOut(ORMModel):
    id: str
    role: str
    content: str
    created_at: datetime


class NodeDetailOut(NodeOut):
    teaching_strategy: str = ""
    search_queries: list[str] = []
    sources: list[SourceOut] = []
    lesson: LessonOut | None = None
    evidence: list[EvidenceOut] = []
    chat: list[ChatMessageOut] = []
    cards: list[dict[str, Any]] | None = None
    prerequisites: list[dict[str, Any]] = []


class QuizQuestionOut(BaseModel):
    id: str
    qtype: str
    stem: str
    options: list[str]
    source_index: int


class QuizOut(BaseModel):
    id: str
    node_id: str
    questions: list[QuizQuestionOut]


class QuizSubmit(BaseModel):
    answers: dict[str, Any]


class QuestionResult(BaseModel):
    id: str
    qtype: str
    correct: bool | None
    score: int
    your_answer: Any
    answer_index: int | None
    explanation: str
    feedback: str = ""


class QuizResultOut(BaseModel):
    quiz_id: str
    node_id: str
    score: int
    results: list[QuestionResult]
    mastery_score: float
    mastery_stars: int
    stars_before: int
    next_actions: list[NextAction]
    summary: str


class CardsOut(BaseModel):
    node_id: str
    cards: list[dict[str, Any]]


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    mode: Literal["tutor", "zhida"] = "tutor"  # tutor = LearnPath 导师（引用本节点来源）；zhida = 知乎直答


class HotItem(BaseModel):
    id: str
    title: str
    heat: str = ""
    excerpt: str = ""
    url: str
    answer_count: int = 0
    follower_count: int = 0
    thumbnail: str = ""


class HealthOut(BaseModel):
    status: str
    llm_provider: str
    llm_model: str
    zhihu_search: list[str]
    zhihu_official: bool
    reader: str
    zhihu_oauth: str = "disabled"
    zhida: bool = False


DashboardOut.model_rebuild()
