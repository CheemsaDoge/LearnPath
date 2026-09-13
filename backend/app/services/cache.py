from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import KVCache, utcnow


def cache_get(db: Session, key: str, max_age_seconds: float | None = None) -> Any | None:
    row = db.get(KVCache, key)
    if row is None:
        return None
    if max_age_seconds is not None and (utcnow() - row.created_at).total_seconds() > max_age_seconds:
        return None
    return row.value


def cache_set(db: Session, key: str, value: Any) -> None:
    row = db.get(KVCache, key)
    if row is None:
        db.add(KVCache(key=key, value=value))
    else:
        row.value = value
        row.created_at = utcnow()
    db.commit()
