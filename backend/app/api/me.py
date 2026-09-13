"""Dashboard (控制台) + profile facts + attachments, all scoped to the current learner (guest or Zhihu user)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.identity import get_current_user
from app.db import get_db
from app.models import Attachment, Graph, ProfileEvent, ProfileFact, User
from app.schemas import AttachmentOut, DashboardOut, GraphOut, MeOut, ProfileEventOut, ProfileFactCreate, ProfileFactOut
from app.services import attachments as attachment_service
from app.services import profile as profile_service
from app.services.progress import GraphProgress

router = APIRouter(prefix="/api", tags=["me"])


def _me(user: User) -> MeOut:
    return MeOut(id=user.id, name=user.name, avatar=user.avatar, headline=user.headline, provider=user.provider, is_guest=user.provider == "guest", created_at=user.created_at)


def _attachment_out(att: Attachment) -> AttachmentOut:
    out = AttachmentOut.model_validate(att)
    out.has_text = bool(att.text)
    return out


def _graph_summary(graph: Graph) -> GraphOut:
    out = GraphOut.model_validate(graph)
    out.goal_text = graph.goal.raw_goal
    if graph.status == "ready":
        progress = GraphProgress(graph)
        out.stats = progress.stats()
        out.next_actions = progress.next_actions(limit=1)
    return out


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(get_current_user)) -> MeOut:
    return _me(user)


@router.get("/me/dashboard", response_model=DashboardOut)
def dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> DashboardOut:
    graphs = db.query(Graph).filter(Graph.user_id == user.id).order_by(Graph.created_at.desc()).all()
    events = db.query(ProfileEvent).filter(ProfileEvent.user_id == user.id).order_by(ProfileEvent.created_at.desc()).limit(40).all()
    attachments = db.query(Attachment).filter(Attachment.user_id == user.id).order_by(Attachment.created_at.desc()).all()
    return DashboardOut(
        user=_me(user),
        facts=[ProfileFactOut.model_validate(f) for f in profile_service.list_facts(db, user.id)],
        events=[ProfileEventOut.model_validate(e) for e in events],
        graphs=[_graph_summary(g) for g in graphs],
        attachments=[_attachment_out(a) for a in attachments],
        stats=profile_service.user_stats(db, user.id),
    )


@router.post("/me/facts", response_model=ProfileFactOut, status_code=201)
def create_fact(payload: ProfileFactCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ProfileFactOut:
    fact = profile_service.add_fact(db, user.id, payload.kind, payload.text, "manual", 1.0)
    if fact is None:
        raise HTTPException(400, "内容为空")
    profile_service.record_event(db, user.id, "manual", f"手动补充档案：{payload.text[:80]}", "fact", fact.id)
    return ProfileFactOut.model_validate(fact)


@router.delete("/me/facts/{fact_id}", status_code=204)
def delete_fact(fact_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    fact = db.get(ProfileFact, fact_id)
    if fact is None or fact.user_id != user.id:
        raise HTTPException(404, "档案条目不存在")
    db.delete(fact)
    db.commit()
    return Response(status_code=204)


@router.post("/attachments", response_model=AttachmentOut, status_code=201)
def upload_attachment(file: UploadFile = File(...), graph_id: str | None = Form(default=None), user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> AttachmentOut:
    try:
        att = attachment_service.save_upload(db, user, file, graph_id or None)
    except attachment_service.AttachmentError as exc:
        raise HTTPException(400, str(exc)) from exc
    return _attachment_out(att)


@router.get("/attachments", response_model=list[AttachmentOut])
def list_attachments(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[AttachmentOut]:
    rows = db.query(Attachment).filter(Attachment.user_id == user.id).order_by(Attachment.created_at.desc()).all()
    return [_attachment_out(a) for a in rows]


@router.get("/attachments/{attachment_id}/download")
def download_attachment(attachment_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> FileResponse:
    att = db.get(Attachment, attachment_id)
    if att is None or att.user_id != user.id:
        raise HTTPException(404, "附件不存在")
    return FileResponse(att.path, filename=att.filename, media_type=att.content_type or "application/octet-stream")


@router.delete("/attachments/{attachment_id}", status_code=204)
def delete_attachment(attachment_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    att = db.get(Attachment, attachment_id)
    if att is None or att.user_id != user.id:
        raise HTTPException(404, "附件不存在")
    attachment_service.delete_attachment(db, att)
    return Response(status_code=204)
