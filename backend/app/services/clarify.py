"""Goal clarification: one sentence in, a few targeted questions out, before any graph is generated."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.llm.base import LLMError, LLMProvider
from app.llm.resilience import call_with_retries
from app.services.fallbacks import fallback_clarify
from app.models import User
from app.schemas import ClarifyOut, ClarifyQuestionOut, ClarifyRequest, LLMClarification
from app.services.attachments import attachment_context
from app.services.profile import profile_context

CLARIFY_SYSTEM = """你是「知径 LearnPath」的学习顾问。学习者刚说出一个学习目标，你要在生成学习路线之前，用 2-4 个问题弄清真正影响路线设计的信息。

要问的通常是：
1. 前置知识：学习者已经掌握了哪些相关基础（给出具体、可点选的选项，例如「会 Python 基础语法」「学过线性代数」）；
2. 目标深度与用途：要达到什么程度（能看懂 / 能动手做 / 能讲给别人 / 应付考试或面试）；
3. 偏好与约束：喜欢先看例子还是先看原理、每次能投入多久、是否需要代码实践。

规则：
- 已在学习者档案或附件中明确的信息不要再问；档案为空时至少要问前置知识。
- 每个问题给 2-5 个简短选项（≤12 字），不要包含「其他」「以上都不是」，界面会自带自由输入。
- intro 用一句话复述你对目标的理解，让学习者确认。
- 简体中文，问题短、口语化。"""


def build_clarify_user(req: ClarifyRequest, profile: str, attachments: str) -> str:
    return (
        f"学习目标：{req.goal}\n"
        f"学习者自述基础：{req.background or '未说明'}\n"
        f"时间预算：{req.time_budget or '未说明'}\n"
        f"学习动机/用途：{req.purpose or '未说明'}\n\n"
        f"学习者档案：\n{profile or '（空）'}\n\n"
        f"附件资料摘要：\n{attachments or '（无）'}"
    )


def clarify(db: Session, llm: LLMProvider, user: User, req: ClarifyRequest) -> ClarifyOut:
    profile = profile_context(db, user.id)
    attachments = attachment_context(db, user.id, req.attachment_ids, per_file=1500, total=4000)
    try:
        plan: LLMClarification = call_with_retries(lambda: llm.structured(system=CLARIFY_SYSTEM, user=build_clarify_user(req, profile, attachments), schema=LLMClarification, effort="low", max_tokens=2500), attempts=2, label="clarify")
    except LLMError:
        plan = fallback_clarify(req.goal)
    questions: list[ClarifyQuestionOut] = []
    for i, q in enumerate(plan.questions[:4], start=1):
        options = [o.strip() for o in q.options if o and o.strip()][:5]
        if not q.question.strip():
            continue
        questions.append(ClarifyQuestionOut(id=q.id.strip() or f"q{i}", question=q.question.strip(), options=options, multiple=bool(q.multiple), why=q.why.strip()))
    hint = "已结合你的学习档案，只问档案里没有的信息。" if profile else ""
    return ClarifyOut(intro=plan.intro.strip(), questions=questions, profile_hint=hint)
