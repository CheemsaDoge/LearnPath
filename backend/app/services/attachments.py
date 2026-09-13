"""Attachments (附件): uploaded syllabi, notes, PDFs… stored on disk, text-extracted, usable as prompt context."""
from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.config import BACKEND_DIR, get_settings
from app.models import Attachment, User
from app.services import profile as profile_service

MAX_BYTES = 20 * 1024 * 1024
TEXT_TYPES = {".txt", ".md", ".markdown", ".csv", ".json", ".py", ".js", ".ts", ".java", ".c", ".cpp", ".h", ".html", ".tex", ".rst", ".yaml", ".yml", ".toml"}


class AttachmentError(RuntimeError):
    pass


def upload_dir() -> Path:
    settings = get_settings()
    base = Path(settings.database_url.replace("sqlite:///", "", 1)).parent if settings.database_url.startswith("sqlite:///") else BACKEND_DIR / "data"
    path = base / "uploads"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_name(name: str) -> str:
    name = Path(name or "file").name
    name = re.sub(r"[^\w.\-一-鿿]+", "_", name).strip("._") or "file"
    return name[:120]


def extract_text(filename: str, data: bytes, content_type: str = "") -> str:
    suffix = Path(filename).suffix.lower()
    try:
        if suffix in TEXT_TYPES or content_type.startswith("text/"):
            return data.decode("utf-8", "ignore")
        if suffix == ".pdf" or content_type == "application/pdf":
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(data))
            return "\n\n".join((page.extract_text() or "") for page in reader.pages[:60])
        if suffix == ".docx":
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                xml = zf.read("word/document.xml").decode("utf-8", "ignore")
            xml = re.sub(r"</w:p>", "\n", xml)
            return re.sub(r"<[^>]+>", "", xml)
    except Exception:  # pragma: no cover - best effort
        return ""
    return ""


def save_upload(db: Session, user: User, upload: UploadFile, graph_id: str | None = None) -> Attachment:
    data = upload.file.read(MAX_BYTES + 1)
    if not data:
        raise AttachmentError("文件为空")
    if len(data) > MAX_BYTES:
        raise AttachmentError("文件超过 20 MB 限制")
    filename = _safe_name(upload.filename or "file")
    text = extract_text(filename, data, upload.content_type or "").strip()
    attachment = Attachment(user_id=user.id, graph_id=graph_id, filename=filename, content_type=upload.content_type or "", size=len(data), path="", text=text[:200_000], summary=" ".join(text.split())[:200])
    db.add(attachment)
    db.flush()
    target = upload_dir() / user.id
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"{attachment.id}_{filename}"
    path.write_bytes(data)
    attachment.path = str(path)
    db.commit()
    profile_service.record_event(db, user.id, "upload", f"上传了附件《{filename}》" + ("（已提取文字）" if text else ""), "attachment", attachment.id, {"size": len(data), "chars": len(text)})
    if text:
        profile_service.extract_facts(user.id, f"学习者上传了资料《{filename}》，开头内容：\n{text[:1500]}", "upload")
    return attachment


def delete_attachment(db: Session, attachment: Attachment) -> None:
    try:
        if attachment.path:
            Path(attachment.path).unlink(missing_ok=True)
    finally:
        db.delete(attachment)
        db.commit()


def attachment_context(db: Session, user_id: str, attachment_ids: list[str], per_file: int = 3000, total: int = 9000) -> str:
    if not attachment_ids:
        return ""
    rows = db.query(Attachment).filter(Attachment.user_id == user_id, Attachment.id.in_(attachment_ids)).all()
    parts: list[str] = []
    used = 0
    for att in rows:
        body = (att.text or "").strip()
        body = body[: min(per_file, max(0, total - used))]
        used += len(body)
        parts.append(f"《{att.filename}》：{body or '（无法提取文字）'}")
        if used >= total:
            break
    return "\n\n".join(parts)
