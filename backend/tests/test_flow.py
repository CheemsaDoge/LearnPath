import json


def _sse_events(response) -> list[dict]:
    events = []
    for line in response.text.split("\n"):
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


def test_end_to_end_learning_flow(client, fake_search):
    health = client.get("/api/health").json()
    assert health["llm_provider"] == "mock"

    created = client.post("/api/goals", json={"goal": "我想在一个月内学会 Transformer", "background": "零基础", "time_budget": "每天1小时", "purpose": "面试"}).json()
    graph = client.get(f"/api/graphs/{created['graph_id']}").json()
    assert graph["status"] == "ready", graph.get("error")
    assert graph["title"]
    types = {n["node_type"] for n in graph["nodes"]}
    assert {"root", "module", "concept"} <= types
    learnable = [n for n in graph["nodes"] if n["node_type"] in {"concept", "practice"}]
    assert learnable and all(n["source_count"] >= 1 for n in learnable)
    assert graph["stats"]["learnable_nodes"] == len(learnable)
    assert graph["next_actions"] and graph["next_actions"][0]["node_id"] == learnable[0]["id"]
    assert any(e["relation"] == "prerequisite" for e in graph["edges"])
    assert fake_search.calls  # sources came from the (fake) Zhihu search

    # search results are cached: creating a second graph with the same goal makes no new search calls
    calls_before = len(fake_search.calls)
    client.post("/api/goals", json={"goal": "我想在一个月内学会 Transformer", "background": "零基础"})
    assert len(fake_search.calls) == calls_before

    node_id = learnable[0]["id"]
    detail = client.get(f"/api/nodes/{node_id}").json()
    assert detail["sources"] and detail["sources"][0]["url"].startswith("https://")
    assert detail["sources"][0]["has_content"] is True
    assert detail["lesson"] is None

    # lesson streams over SSE and is persisted
    events = _sse_events(client.post(f"/api/nodes/{node_id}/lesson"))
    assert events[0]["citations"] and events[-1]["done"] is True
    text = "".join(e.get("delta", "") for e in events)
    assert "一句话定义" in text
    detail = client.get(f"/api/nodes/{node_id}").json()
    assert detail["lesson"]["content_md"] == text.strip()

    # quiz → grade → mastery → next actions
    quiz = client.post(f"/api/nodes/{node_id}/quiz").json()
    assert len(quiz["questions"]) == 4 and quiz["questions"][-1]["qtype"] == "feynman"
    assert "answer_index" not in quiz["questions"][0]
    answers = {q["id"]: 1 for q in quiz["questions"] if q["qtype"] == "single"}
    answers[quiz["questions"][-1]["id"]] = "它是一种把输入映射到输出的方法，例如翻译句子；关键在于注意力机制，让模型关注相关的词。"
    result = client.post(f"/api/quizzes/{quiz['id']}/submit", json={"answers": answers}).json()
    assert 0 <= result["score"] <= 100
    assert result["mastery_stars"] >= 1
    assert result["results"][0]["correct"] is True
    assert result["next_actions"]
    assert client.post(f"/api/quizzes/{quiz['id']}/submit", json={"answers": answers}).status_code == 409

    graph = client.get(f"/api/graphs/{created['graph_id']}").json()
    node = next(n for n in graph["nodes"] if n["id"] == node_id)
    assert node["attempts"] == 1 and node["mastery_stars"] == result["mastery_stars"]
    assert graph["stats"]["started_nodes"] == 1

    # cards, chat, export
    cards = client.post(f"/api/nodes/{node_id}/cards").json()
    assert len(cards["cards"]) >= 3
    events = _sse_events(client.post(f"/api/nodes/{node_id}/chat", json={"question": "为什么需要注意力机制？"}))
    assert events[-1]["done"] is True
    detail = client.get(f"/api/nodes/{node_id}").json()
    assert [m["role"] for m in detail["chat"]] == ["user", "assistant"]
    assert any(e["kind"] == "quiz" for e in detail["evidence"])

    md = client.get(f"/api/graphs/{created['graph_id']}/export.md").text
    assert md.startswith("# ") and "知乎来源" in md and "https://" in md

    listed = client.get("/api/graphs").json()
    assert listed[0]["id"] and listed[0]["goal_text"]


def test_unlock_and_recommendation_logic(client):
    created = client.post("/api/goals", json={"goal": "学会复变函数中的留数定理"}).json()
    graph = client.get(f"/api/graphs/{created['graph_id']}").json()
    learnable = [n for n in graph["nodes"] if n["node_type"] in {"concept", "practice"}]
    first, second = learnable[0], learnable[1]
    assert first["unlocked"] is True
    assert second["unlocked"] is False  # sequential prerequisite from the mock plan
    detail = client.get(f"/api/nodes/{second['id']}").json()
    assert detail["prerequisites"] and detail["prerequisites"][0]["satisfied"] is False
    assert any("建议先学" in a["reason"] for a in graph["next_actions"] if a["node_id"] == second["id"]) or graph["next_actions"][0]["node_id"] == first["id"]


def test_retry_and_delete(client):
    created = client.post("/api/goals", json={"goal": "学习供应链金融"}).json()
    graph = client.get(f"/api/graphs/{created['graph_id']}").json()
    node_id = next(n["id"] for n in graph["nodes"] if n["node_type"] == "concept")
    quiz = client.post(f"/api/nodes/{node_id}/quiz").json()
    client.post(f"/api/quizzes/{quiz['id']}/submit", json={"answers": {}})
    client.post(f"/api/nodes/{node_id}/cards")
    client.post(f"/api/nodes/{node_id}/chat", json={"question": "什么是供应链金融？"})
    retried = client.post(f"/api/graphs/{created['graph_id']}/retry").json()
    assert retried["graph_id"] == created["graph_id"]
    graph = client.get(f"/api/graphs/{created['graph_id']}").json()
    assert graph["status"] == "ready" and graph["nodes"]
    node_id = next(n["id"] for n in graph["nodes"] if n["node_type"] == "concept")
    client.post(f"/api/nodes/{node_id}/quiz")
    assert client.delete(f"/api/graphs/{created['graph_id']}").status_code == 204
    assert client.get(f"/api/graphs/{created['graph_id']}").status_code == 404
