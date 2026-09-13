from app.config import get_settings
from app.services import oauth


def test_login_disabled_without_config(client):
    assert client.get("/api/auth/me").json() == {"enabled": False, "stage": "test", "provider": "zhihu", "login_url": None, "user": None}
    assert client.get("/api/auth/zhihu/login", follow_redirects=False).status_code == 503


def test_full_oauth_round_trip(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "zhihu_oauth_app_id", "app123")
    monkeypatch.setattr(settings, "zhihu_oauth_app_key", "sec")
    monkeypatch.setattr(settings, "public_origin", "https://learn.example")

    assert client.get("/api/auth/me").json()["enabled"] is True
    guest_id = client.get("/api/me").json()["id"]
    client.post("/api/me/facts", json={"kind": "skill", "text": "访客期间记录：会 SQL"})

    r = client.get("/api/auth/zhihu/login?next=/g/abc", follow_redirects=False)
    assert r.status_code == 302
    location = r.headers["location"]
    assert location.startswith("https://openapi.zhihu.com/authorize?redirect_uri=https%3A%2F%2Flearn.example%2Fapi%2Fauth%2Fzhihu%2Fcallback&app_id=app123&response_type=code&state=")
    state = location.split("state=")[1]
    assert client.cookies.get(oauth.STATE_COOKIE) == state

    calls = {}

    def fake_exchange(settings, code, timeout=20.0):
        calls["code"] = code
        return {"access_token": "tok123", "token_type": "bearer"}

    def fake_profile(settings, token, timeout=20.0):
        calls["token"] = token
        return {"uid": "969570047710216200", "hash_id": "0e4f7a", "fullname": "刘看山", "avatar_path": "https://pic.zhimg.com/a.png", "headline": "知乎吉祥物", "code": 20000}

    monkeypatch.setattr(oauth, "exchange_code", fake_exchange)
    monkeypatch.setattr(oauth, "fetch_profile", fake_profile)

    r = client.get(f"/api/auth/zhihu/callback?authorization_code=c0de&state={state}", follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == "/g/abc"
    assert calls == {"code": "c0de", "token": "tok123"}
    me = client.get("/api/auth/me").json()
    assert me["user"]["name"] == "刘看山" and me["user"]["avatar"].endswith("a.png")
    real = client.get("/api/me").json()
    assert real["is_guest"] is False and real["id"] != guest_id
    dash = client.get("/api/me/dashboard").json()
    assert any("会 SQL" in f["text"] for f in dash["facts"])  # guest data merged
    assert any(e["kind"] == "login" for e in dash["events"])
    from app.db import session_factory
    from app.models import User

    with session_factory()() as db:
        assert db.query(User).filter(User.provider_uid == "969570047710216200").one().profile["hash_id"] == "0e4f7a"

    # tampered / missing state is rejected
    r = client.get("/api/auth/zhihu/callback?authorization_code=x&state=bad.state", follow_redirects=False)
    assert r.status_code == 400
    r = client.get("/api/auth/zhihu/callback?authorization_code=x", follow_redirects=False)
    assert r.status_code == 400

    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").json()["user"] is None


def test_state_signature_and_expiry():
    settings = get_settings()
    state = oauth.make_state(settings, "/g/1")
    assert oauth.verify_state(settings, state) == "/g/1"
    forged = state[:-4] + "0000"
    try:
        oauth.verify_state(settings, forged)
        assert False, "forged state accepted"
    except oauth.OAuthError:
        pass
    assert oauth.verify_state(settings, oauth.make_state(settings, "//evil.com")) == "/"


def test_profile_parsing_keeps_big_uid_and_detects_errors(monkeypatch):
    import httpx

    from app.config import get_settings

    settings = get_settings()

    class FakeResp:
        def __init__(self, text, status=200):
            self.text, self.status_code = text, status

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url, headers=None):
            return FakeClient.resp

    monkeypatch.setattr(httpx, "Client", FakeClient)
    FakeClient.resp = FakeResp('{"uid": 969570047710216200, "fullname": "A", "avatar_path": "", "headline": "", "code": 20000}')
    raw = oauth.fetch_profile(settings, "tok")
    assert raw["uid"] == "969570047710216200"  # lossless
    assert oauth.normalize_profile(raw)["uid"] == "969570047710216200"
    FakeClient.resp = FakeResp('{"code": 401, "data": "Access token is not valid"}')
    try:
        oauth.fetch_profile(settings, "tok")
        assert False
    except oauth.OAuthError as exc:
        assert "401" in str(exc)
