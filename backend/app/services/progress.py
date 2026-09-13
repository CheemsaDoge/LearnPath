"""Mastery, unlocking and next-step recommendation (LearnGraph's M and A stages)."""
from __future__ import annotations

from collections import defaultdict

from app.models import Graph, Node, utcnow
from app.schemas import GraphStats, NextAction

STAR_THRESHOLDS = ((85, 3), (65, 2), (40, 1))


def stars_for(score: float) -> int:
    for threshold, stars in STAR_THRESHOLDS:
        if score >= threshold:
            return stars
    return 0


def update_mastery(node: Node, score: float) -> None:
    score = max(0.0, min(100.0, float(score)))
    node.mastery_score = round(score if node.attempts == 0 else 0.6 * score + 0.4 * node.mastery_score, 1)
    node.attempts += 1
    node.mastery_stars = stars_for(node.mastery_score)
    node.last_studied_at = utcnow()


class GraphProgress:
    """Derived view over a graph: learnable nodes, unlock state, module completion."""

    def __init__(self, graph: Graph) -> None:
        self.graph = graph
        self.nodes = {n.id: n for n in graph.nodes}
        self.children: dict[str | None, list[Node]] = defaultdict(list)
        for node in graph.nodes:
            self.children[node.parent_id].append(node)
        for lst in self.children.values():
            lst.sort(key=lambda n: n.order_index)
        self.prereqs: dict[str, list[Node]] = defaultdict(list)
        for edge in graph.edges:
            if edge.relation == "prerequisite" and edge.source_id in self.nodes and edge.target_id in self.nodes:
                self.prereqs[edge.target_id].append(self.nodes[edge.source_id])

    # ----- classification
    def is_learnable(self, node: Node) -> bool:
        if node.node_type == "root":
            return False
        if node.node_type == "module":
            return not self.children.get(node.id)
        return True

    def learnable_nodes(self) -> list[Node]:
        return [n for n in self.graph.nodes if self.is_learnable(n)]

    # ----- mastery
    def stars(self, node: Node) -> int:
        if self.is_learnable(node):
            return node.mastery_stars
        kids = [k for k in self.children.get(node.id, []) if self.is_learnable(k) or self.children.get(k.id)]
        if not kids:
            return 0
        return int(round(sum(self.stars(k) for k in kids) / len(kids)))

    def module_started_ratio(self, module: Node) -> float:
        kids = [k for k in self.children.get(module.id, []) if self.is_learnable(k)]
        if not kids:
            return 1.0 if module.mastery_stars >= 1 else 0.0
        return sum(1 for k in kids if k.mastery_stars >= 1) / len(kids)

    def prereq_satisfied(self, prereq: Node) -> bool:
        if self.is_learnable(prereq):
            return prereq.mastery_stars >= 1
        return self.module_started_ratio(prereq) >= 0.5

    def is_unlocked(self, node: Node) -> bool:
        if not self.is_learnable(node):
            return True
        for prereq in self.prereqs.get(node.id, []):
            if not self.prereq_satisfied(prereq):
                return False
        parent = self.nodes.get(node.parent_id or "")
        if parent is not None:
            for prereq in self.prereqs.get(parent.id, []):
                if not self.prereq_satisfied(prereq):
                    return False
        return True

    def blocking_prereqs(self, node: Node) -> list[Node]:
        blocking = [p for p in self.prereqs.get(node.id, []) if not self.prereq_satisfied(p)]
        parent = self.nodes.get(node.parent_id or "")
        if parent is not None:
            blocking += [p for p in self.prereqs.get(parent.id, []) if not self.prereq_satisfied(p)]
        return blocking

    # ----- stats & recommendation
    def stats(self) -> GraphStats:
        learnable = self.learnable_nodes()
        mastered = [n for n in learnable if n.mastery_stars >= 2]
        started = [n for n in learnable if n.attempts > 0]
        minutes_total = sum(n.est_minutes for n in learnable)
        minutes_remaining = sum(n.est_minutes for n in learnable if n.mastery_stars < 2)
        return GraphStats(
            total_nodes=len(self.graph.nodes),
            learnable_nodes=len(learnable),
            mastered_nodes=len(mastered),
            started_nodes=len(started),
            minutes_total=minutes_total,
            minutes_remaining=minutes_remaining,
            completion=round(len(mastered) / len(learnable), 3) if learnable else 0.0,
        )

    def next_actions(self, limit: int = 3) -> list[NextAction]:
        candidates = [n for n in self.learnable_nodes() if n.mastery_stars < 3]
        if not candidates:
            return []

        def sort_key(n: Node):
            unlocked = self.is_unlocked(n)
            return (0 if unlocked else 1, 0 if n.attempts == 0 else 1, n.order_index)

        actions: list[NextAction] = []
        for node in sorted(candidates, key=sort_key)[:limit]:
            blocking = self.blocking_prereqs(node)
            if blocking:
                reason = "建议先学「" + "」「".join(p.label for p in blocking[:2]) + "」"
            elif node.attempts == 0:
                done_prereqs = [p for p in self.prereqs.get(node.id, []) if self.prereq_satisfied(p)]
                reason = f"前置「{done_prereqs[0].label}」已入门，正是时候" if done_prereqs else "路线上的下一站"
            elif node.mastery_stars < 2:
                reason = f"上次得分 {node.mastery_score:.0f}，再练一次巩固"
            else:
                reason = "冲刺三星：再做一次费曼解释"
            actions.append(NextAction(node_id=node.id, label=node.label, reason=reason, est_minutes=node.est_minutes))
        return actions
