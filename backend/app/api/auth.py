from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.services import oauth

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


class AuthStatus(BaseModel):
    enabled: bool
    stage: str = "test"  # 知乎 OAuth 接入处于测试状态
    provider: str = "zhihu"
    login_url: str | None = None
    user: dict | None = None


def _cookie_secure(request: Request) -> bool:
    return request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"


@router.get("/me", response_model=AuthStatus)
def me(request: Request, db: Session = Depends(get_db)) -> AuthStatus:
    settings = get_settings()
    user = oauth.resolve_session(db, request.cookies.get(oauth.SESSION_COOKIE))
    return AuthStatus(
        enabled=settings.zhihu_oauth_enabled,
        login_url="/api/auth/zhihu/login" if settings.zhihu_oauth_enabled else None,
        user={"id": user.id, "name": user.name, "avatar": user.avatar, "headline": user.headline, "provider": user.provider} if user else None,
    )


@router.get("/zhihu/login")
def zhihu_login(request: Request, next: str = "/") -> RedirectResponse:
    settings = get_settings()
    if not settings.zhihu_oauth_enabled:
        raise HTTPException(503, "知乎登录尚未配置（测试状态）：请在 backend/.env 填写 LEARNWAY_ZHIHU_OAUTH_* 后重启")
    state = oauth.make_state(settings, next)
    resp = RedirectResponse(oauth.authorize_url(settings, state), status_code=302)
    resp.set_cookie(oauth.STATE_COOKIE, state, max_age=oauth.STATE_TTL_SECONDS, httponly=True, samesite="lax", secure=_cookie_secure(request))
    return resp


@router.get("/zhihu/callback")
def zhihu_callback(request: Request, code: str | None = None, state: str | None = None, error: str | None = None, db: Session = Depends(get_db)):
    settings = get_settings()
    if error:
        return RedirectResponse(f"/?login_error={error}", status_code=302)
    if not code or not state:
        raise HTTPException(400, "缺少 code 或 state")
    if request.cookies.get(oauth.STATE_COOKIE) != state:
        raise HTTPException(400, "state 与本地登录请求不匹配，请重新登录")
    try:
        next_path = oauth.verify_state(settings, state)
        token_payload = oauth.exchange_code(settings, code)
        raw_profile = oauth.fetch_profile(settings, token_payload["access_token"])
    except oauth.OAuthError as exc:
        log.warning("zhihu oauth failed: %s", exc)
        return RedirectResponse("/?login_error=" + str(exc)[:120], status_code=302)
    profile = oauth.normalize_profile(raw_profile, fallback_uid=str(token_payload.get("uid") or token_payload.get("user_id") or token_payload.get("open_id") or ""))
    if not profile["uid"]:
        return RedirectResponse("/?login_error=" + "用户信息中缺少唯一标识", status_code=302)
    user = oauth.upsert_user(db, profile, raw_profile)
    session = oauth.create_session(db, user, token_payload["access_token"])
    resp = RedirectResponse(next_path, status_code=302)
    resp.set_cookie(oauth.SESSION_COOKIE, session.id, max_age=int(oauth.SESSION_TTL.total_seconds()), httponly=True, samesite="lax", secure=_cookie_secure(request))
    resp.delete_cookie(oauth.STATE_COOKIE)
    return resp


@router.post("/logout", status_code=204)
def logout(request: Request, db: Session = Depends(get_db)) -> Response:
    oauth.destroy_session(db, request.cookies.get(oauth.SESSION_COOKIE))
    resp = Response(status_code=204)
    resp.delete_cookie(oauth.SESSION_COOKIE)
    return resp
