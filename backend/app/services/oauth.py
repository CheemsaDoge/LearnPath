"""Zhihu OAuth 2.0 (authorization-code) login — 测试状态.

Endpoints, client credentials and scopes are configuration-driven so the integration can be aligned with the
official quickstart without code changes. Only the profile-field mapping (`normalize_profile`) may need tweaks.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
import urllib.parse
from datetime import timedelta
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import LoginSession, User, utcnow

SESSION_COOKIE = "learnway_session"
STATE_COOKIE = "learnway_oauth_state"
SESSION_TTL = timedelta(days=30)
STATE_TTL_SECONDS = 600


class OAuthError(RuntimeError):
    pass


# ----------------------------------------------------------------------------- state (signed, stateless)
def _sign(secret: str, payload: str) -> str:
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()[:32]


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


def _unb64(text: str) -> str:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4)).decode()


def make_state(settings: Settings, next_path: str = "/") -> str:
    payload = f"{int(time.time())}.{secrets.token_urlsafe(12)}.{_b64(next_path)}"
    return f"{payload}.{_sign(settings.session_secret, payload)}"


def verify_state(settings: Settings, state: str) -> str:
    """Return the `next` path if the state is authentic and fresh, else raise."""
    try:
        ts, nonce, next_q, sig = state.split(".")
    except ValueError as exc:
        raise OAuthError("state 格式不正确") from exc
    payload = f"{ts}.{nonce}.{next_q}"
    if not hmac.compare_digest(sig, _sign(settings.session_secret, payload)):
        raise OAuthError("state 签名校验失败")
    if time.time() - int(ts) > STATE_TTL_SECONDS:
        raise OAuthError("登录请求已过期，请重试")
    try:
        next_path = _unb64(next_q)
    except Exception as exc:  # pragma: no cover - defensive
        raise OAuthError("state 内容无法解析") from exc
    return next_path if next_path.startswith("/") and not next_path.startswith("//") else "/"


# ----------------------------------------------------------------------------- provider calls
def authorize_url(settings: Settings, state: str) -> str:
    params = {
        "response_type": "code",
        "client_id": settings.zhihu_oauth_client_id,
        "redirect_uri": settings.resolved_redirect_uri,
        "state": state,
    }
    if settings.zhihu_oauth_scope:
        params["scope"] = settings.zhihu_oauth_scope
    sep = "&" if "?" in settings.zhihu_oauth_authorize_url else "?"
    return settings.zhihu_oauth_authorize_url + sep + urllib.parse.urlencode(params)


def exchange_code(settings: Settings, code: str, timeout: float = 20.0) -> dict[str, Any]:
    """Authorization code → token response (dict with at least `access_token`)."""
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.resolved_redirect_uri,
        "client_id": settings.zhihu_oauth_client_id,
        "client_secret": settings.zhihu_oauth_client_secret,
    }
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(settings.zhihu_oauth_token_url, data=data, headers={"Accept": "application/json"})
    except httpx.HTTPError as exc:
        raise OAuthError(f"无法连接授权服务器：{exc}") from exc
    if resp.status_code >= 400:
        raise OAuthError(f"换取 token 失败 ({resp.status_code}): {resp.text[:200]}")
    try:
        payload = resp.json()
    except ValueError:
        payload = dict(urllib.parse.parse_qsl(resp.text))
    token = payload.get("access_token") or (payload.get("data") or {}).get("access_token")
    if not token:
        raise OAuthError(f"token 响应中没有 access_token: {str(payload)[:200]}")
    if "access_token" not in payload:
        payload = {**payload, "access_token": token}
    return payload


def fetch_profile(settings: Settings, token: str, timeout: float = 20.0) -> dict[str, Any]:
    if not settings.zhihu_oauth_userinfo_url:
        return {}
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(settings.zhihu_oauth_userinfo_url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
    except httpx.HTTPError as exc:
        raise OAuthError(f"无法获取用户信息：{exc}") from exc
    if resp.status_code >= 400:
        raise OAuthError(f"获取用户信息失败 ({resp.status_code}): {resp.text[:200]}")
    payload = resp.json()
    return payload.get("data") if isinstance(payload, dict) and isinstance(payload.get("data"), dict) else payload


def normalize_profile(raw: dict[str, Any], fallback_uid: str = "") -> dict[str, str]:
    """Map the provider's user object onto our User fields (tolerant to several naming conventions)."""

    def pick(*keys: str) -> str:
        for k in keys:
            v = raw.get(k)
            if v not in (None, ""):
                return str(v)
        return ""

    return {
        "uid": pick("id", "uid", "open_id", "openid", "url_token", "user_id") or fallback_uid,
        "name": pick("name", "nickname", "screen_name", "username") or "知乎用户",
        "avatar": pick("avatar_url", "avatar", "avatar_url_template", "head_url"),
        "headline": pick("headline", "bio", "description"),
    }


# ----------------------------------------------------------------------------- session
def upsert_user(db: Session, profile: dict[str, str], raw: dict[str, Any]) -> User:
    user = db.query(User).filter(User.provider == "zhihu", User.provider_uid == profile["uid"]).one_or_none()
    if user is None:
        user = User(provider="zhihu", provider_uid=profile["uid"])
        db.add(user)
    user.name = profile["name"]
    user.avatar = profile["avatar"]
    user.headline = profile["headline"]
    user.profile = raw
    user.last_login_at = utcnow()
    db.flush()
    return user


def create_session(db: Session, user: User, access_token: str = "") -> LoginSession:
    session = LoginSession(id=secrets.token_urlsafe(32), user_id=user.id, access_token=access_token, expires_at=utcnow() + SESSION_TTL)
    db.add(session)
    db.commit()
    return session


def resolve_session(db: Session, session_id: str | None) -> User | None:
    if not session_id:
        return None
    session = db.get(LoginSession, session_id)
    if session is None or session.expires_at < utcnow():
        return None
    return session.user


def destroy_session(db: Session, session_id: str | None) -> None:
    if not session_id:
        return
    session = db.get(LoginSession, session_id)
    if session is not None:
        db.delete(session)
        db.commit()
