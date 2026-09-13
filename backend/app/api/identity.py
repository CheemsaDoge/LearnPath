"""Who is the learner? A Zhihu-OAuth user when logged in, otherwise a persistent guest identity (cookie-bound).

The guest identity lets the profile / dashboard / attachments work before OAuth credentials are issued; on the first
Zhihu login the guest's data is merged into the real account (see services.profile.merge_guest).
"""
from __future__ import annotations

from fastapi import Depends, Request, Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.ids import new_id
from app.models import User
from app.services import oauth

GUEST_COOKIE = "learnpath_guest"
GUEST_TTL = 365 * 24 * 3600


def cookie_secure(request: Request) -> bool:
    return request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"


def get_current_user(request: Request, response: Response, db: Session = Depends(get_db)) -> User:
    user = oauth.resolve_session(db, request.cookies.get(oauth.SESSION_COOKIE))
    if user is not None:
        return user
    guest_id = request.cookies.get(GUEST_COOKIE)
    guest = db.get(User, guest_id) if guest_id else None
    if guest is None or guest.provider != "guest":
        guest = User(provider="guest", provider_uid=new_id("guest_"), name="访客学习者", headline="尚未登录知乎，档案暂存在本设备")
        db.add(guest)
        db.commit()
        response.set_cookie(GUEST_COOKIE, guest.id, max_age=GUEST_TTL, httponly=True, samesite="lax", secure=cookie_secure(request))
    return guest


def current_guest(request: Request, db: Session) -> User | None:
    guest_id = request.cookies.get(GUEST_COOKIE)
    guest = db.get(User, guest_id) if guest_id else None
    return guest if guest is not None and guest.provider == "guest" else None
