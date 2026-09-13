import json

from app.llm.base import LLMError
from app.llm import factory
from app.llm.resilience import call_with_retries


class FlakyProvider:
    """Fails N times, then delegates to the mock provider."""

    name = "flaky"
    model = "flaky"

    def __init__(self, fail_times: int):
        from app.llm.mock_provider import MockProvider

        self.inner = MockProvider()
        self.fail_times = fail_times
        self.calls = 0

    def _maybe_fail(self):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise LLMError("Service Unavailable 503")

    def structured(self, **kw):
        self._maybe_fail()
        return self.inner.structured(**kw)

    def stream(self, **kw):
        self._maybe_fail()
        yield from self.inner.stream(**kw)

    def complete(self, **kw):
        self._maybe_fail()
        return self.inner.complete(**kw)


def _sse(resp):
    return [json.loads(l[6:]) for l in resp.text.split("\n") if l.startswith("data: ")]


def test_call_with_retries_recovers(monkeypatch):
    monkeypatch.setattr("app.llm.resilience.time.sleep", lambda *_: None)
    p = FlakyProvider(fail_times=2)
    assert call_with_retries(lambda: p.complete(system="", user="学习目标：x"), attempts=3) != ""
    assert p.calls == 3


def test_everything_degrades_gracefully_when_llm_is_down(client, monkeypatch):
    monkeypatch.setattr("app.llm.resilience.time.sleep", lambda *_: None)
    dead = FlakyProvider(fail_times=10**6)
    monkeypatch.setattr(factory, "get_llm", lambda: dead)
    monkeypatch.setattr("app.api.routes.get_llm", lambda: dead)
    monkeypatch.setattr("app.services.graph_builder.get_llm", lambda: dead)

    # clarification still returns questions
    q = client.post("/api/goals/clarify", json={"goal": "学习操作系统"}).json()
    assert len(q["questions"]) >= 2

    # graph still gets generated (skeleton) and is marked degraded, never "failed"
    created = client.post("/api/goals", json={"goal": "学习操作系统"}).json()
    graph = client.get(f"/api/graphs/{created['graph_id']}").json()
    assert graph["status"] == "ready" and graph["degraded"] is True and graph["nodes"]
    node_id = next(n["id"] for n in graph["nodes"] if n["node_type"] == "concept")

    # lesson streams fallback content with sources, flagged degraded
    ev = _sse(client.post(f"/api/nodes/{node_id}/lesson"))
    assert ev[-1]["done"] is True and ev[-1]["degraded"] is True
    assert "临时版本" in "".join(e.get("delta", "") for e in ev)
    assert not any("error" in e for e in ev)

    # quiz / grading / cards / chat all still work
    quiz = client.post(f"/api/nodes/{node_id}/quiz").json()
    assert len(quiz["questions"]) >= 2
    answers = {qq["id"]: (0 if qq["qtype"] == "single" else "这是我的解释，包含定义和例子。") for qq in quiz["questions"]}
    res = client.post(f"/api/quizzes/{quiz['id']}/submit", json={"answers": answers}).json()
    assert 0 <= res["score"] <= 100
    assert client.post(f"/api/nodes/{node_id}/cards").json()["cards"]
    ev = _sse(client.post(f"/api/nodes/{node_id}/chat", json={"question": "为什么？"}))
    assert ev[-1]["done"] is True and "来源" in "".join(e.get("delta", "") for e in ev)


def test_lesson_retries_then_succeeds(client, monkeypatch):
    monkeypatch.setattr("app.llm.resilience.time.sleep", lambda *_: None)
    flaky = FlakyProvider(fail_times=1)
    monkeypatch.setattr("app.api.routes.get_llm", lambda: flaky)
    created = client.post("/api/goals", json={"goal": "学习计算机网络"}).json()
    graph = client.get(f"/api/graphs/{created['graph_id']}").json()
    node_id = next(n["id"] for n in graph["nodes"] if n["node_type"] == "concept")
    ev = _sse(client.post(f"/api/nodes/{node_id}/lesson"))
    assert any("status" in e for e in ev) and ev[-1]["degraded"] is False
    assert "一句话定义" in "".join(e.get("delta", "") for e in ev)
