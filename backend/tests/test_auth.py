from app.config import get_settings
from app.services import oauth


def test_login_disabled_without_config(client):
    assert client.get("/api/auth/me").json() == {"enabled": False, "stage": "test", "provider": "zhihu", "login_url": None, "user": None}
    assert client.get("/api/auth/zhihu/login", follow_redirects=False).status_code == 503


def test_full_oauth_round_trip(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "zhihu_oauth_client_id", "cid")
    monkeypatch.setattr(settings, "zhihu_oauth_client_secret", "sec")
    monkeypatch.setattr(settings, "zhihu_oauth_authorize_url", "https://oauth.example/authorize")
    monkeypatch.setattr(settings, "zhihu_oauth_token_url", "https://oauth.example/token")
    monkeypatch.setattr(settings, "zhihu_oauth_userinfo_url", "https://oauth.example/me")
    monkeypatch.setattr(settings, "public_origin", "https://learn.example")

    assert client.get("/api/auth/me").json()["enabled"] is True

    r = client.get("/api/auth/zhihu/login?next=/g/abc", follow_redirects=False)
    assert r.status_code == 302
    location = r.headers["location"]
    assert location.startswith("https://oauth.example/authorize?response_type=code&client_id=cid")
    assert "redirect_uri=https%3A%2F%2Flearn.example%2Fapi%2Fauth%2Fzhihu%2Fcallback" in location
    state = location.split("state=")[1]
    assert client.cookies.get(oauth.STATE_COOKIE) == state

    calls = {}

    def fake_exchange(settings, code, timeout=20.0):
        calls["code"] = code
        return {"access_token": "tok123", "token_type": "bearer"}

    def fake_profile(settings, token, timeout=20.0):
        calls["token"] = token
        return {"id": "zh_42", "name": "刘看山", "avatar_url": "https://pic.zhimg.com/a.png", "headline": "知乎吉祥物"}

    monkeypatch.setattr(oauth, "exchange_code", fake_exchange)
    monkeypatch.setattr(oauth, "fetch_profile", fake_profile)

    r = client.get(f"/api/auth/zhihu/callback?code=c0de&state={state}", follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == "/g/abc"
    assert calls == {"code": "c0de", "token": "tok123"}
    me = client.get("/api/auth/me").json()
    assert me["user"]["name"] == "刘看山" and me["user"]["avatar"].endswith("a.png")

    # tampered state is rejected
    r = client.get("/api/auth/zhihu/callback?code=x&state=bad.state", follow_redirects=False)
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
