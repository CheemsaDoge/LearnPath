from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.ids import new_id


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("goal_"))
    raw_goal: Mapped[str] = mapped_column(Text)
    background: Mapped[str] = mapped_column(String(64), default="")
    time_budget: Mapped[str] = mapped_column(String(64), default="")
    purpose: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    graphs: Mapped[list["Graph"]] = relationship(back_populates="goal")


class Graph(Base):
    __tablename__ = "graphs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("g_"))
    goal_id: Mapped[str] = mapped_column(ForeignKey("goals.id"))
    title: Mapped[str] = mapped_column(String(200), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    learner_profile: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="generating")  # generating|grounding|ready|failed
    error: Mapped[str] = mapped_column(Text, default="")
    progress: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    provider_trace: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    goal: Mapped[Goal] = relationship(back_populates="graphs")
    nodes: Mapped[list["Node"]] = relationship(back_populates="graph", cascade="all, delete-orphan", order_by="Node.order_index")
    edges: Mapped[list["Edge"]] = relationship(back_populates="graph", cascade="all, delete-orphan")


class Node(Base):
    __tablename__ = "nodes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("n_"))
    graph_id: Mapped[str] = mapped_column(ForeignKey("graphs.id"), index=True)
    ref: Mapped[str] = mapped_column(String(80), default="")
    label: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    node_type: Mapped[str] = mapped_column(String(32), default="concept")  # root|module|concept|practice
    layer: Mapped[int] = mapped_column(Integer, default=0)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    parent_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    weight: Mapped[int] = mapped_column(Integer, default=50)
    difficulty: Mapped[int] = mapped_column(Integer, default=2)
    est_minutes: Mapped[int] = mapped_column(Integer, default=30)
    teaching_strategy: Mapped[str] = mapped_column(Text, default="")
    search_queries: Mapped[list[str]] = mapped_column(JSON, default=list)
    grounding_status: Mapped[str] = mapped_column(String(32), default="pending")  # pending|done|failed|skipped
    mastery_score: Mapped[float] = mapped_column(Float, default=0.0)
    mastery_stars: Mapped[int] = mapped_column(Integer, default=0)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_studied_at: Mapped[datetime | None] = mapped_column(nullable=True)

    graph: Mapped[Graph] = relationship(back_populates="nodes")
    sources: Mapped[list["NodeSource"]] = relationship(back_populates="node", cascade="all, delete-orphan", order_by="NodeSource.rank")
    lessons: Mapped[list["Lesson"]] = relationship(back_populates="node", cascade="all, delete-orphan")
    evidence: Mapped[list["Evidence"]] = relationship(back_populates="node", cascade="all, delete-orphan")


class Edge(Base):
    __tablename__ = "edges"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("e_"))
    graph_id: Mapped[str] = mapped_column(ForeignKey("graphs.id"), index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("nodes.id"))
    target_id: Mapped[str] = mapped_column(ForeignKey("nodes.id"))
    relation: Mapped[str] = mapped_column(String(32), default="prerequisite")  # contains|prerequisite|related

    graph: Mapped[Graph] = relationship(back_populates="edges")


class Source(Base):
    """A piece of Zhihu content (question / answer / article) we can cite."""

    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("s_"))
    url: Mapped[str] = mapped_column(String(500), unique=True, index=True)
    kind: Mapped[str] = mapped_column(String(32), default="other")  # question|answer|article|other
    title: Mapped[str] = mapped_column(String(300), default="")
    snippet: Mapped[str] = mapped_column(Text, default="")
    content: Mapped[str] = mapped_column(Text, default="")
    author: Mapped[str] = mapped_column(String(120), default="")
    votes: Mapped[int] = mapped_column(Integer, default=0)
    origin: Mapped[str] = mapped_column(String(32), default="web")  # official|web|hot
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    fetched_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class NodeSource(Base):
    __tablename__ = "node_sources"
    __table_args__ = (UniqueConstraint("node_id", "source_id", name="uq_node_source"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    node_id: Mapped[str] = mapped_column(ForeignKey("nodes.id"), index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"))
    rank: Mapped[int] = mapped_column(Integer, default=0)
    query: Mapped[str] = mapped_column(String(200), default="")

    node: Mapped[Node] = relationship(back_populates="sources")
    source: Mapped[Source] = relationship()


class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("l_"))
    node_id: Mapped[str] = mapped_column(ForeignKey("nodes.id"), index=True)
    content_md: Mapped[str] = mapped_column(Text, default="")
    citations: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    node: Mapped[Node] = relationship(back_populates="lessons")


class Quiz(Base):
    __tablename__ = "quizzes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("q_"))
    node_id: Mapped[str] = mapped_column(ForeignKey("nodes.id"), index=True)
    questions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    submitted: Mapped[bool] = mapped_column(default=False)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class CardDeck(Base):
    __tablename__ = "card_decks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("c_"))
    node_id: Mapped[str] = mapped_column(ForeignKey("nodes.id"), index=True)
    cards: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Evidence(Base):
    """Every learning action leaves a traceable evidence record (LearnGraph's E in G-R-E-M-A)."""

    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("ev_"))
    node_id: Mapped[str] = mapped_column(ForeignKey("nodes.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32))  # quiz|feynman|lesson|chat
    score: Mapped[float] = mapped_column(Float, default=0.0)
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    node: Mapped[Node] = relationship(back_populates="evidence")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("m_"))
    node_id: Mapped[str] = mapped_column(ForeignKey("nodes.id"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class KVCache(Base):
    """Generic cache for search results and fetched pages (keeps demos fast and reproducible)."""

    __tablename__ = "kv_cache"

    key: Mapped[str] = mapped_column(String(600), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
