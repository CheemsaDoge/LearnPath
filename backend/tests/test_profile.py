import io


def test_guest_identity_persists_and_dashboard_works(client):
    me = client.get("/api/me").json()
    assert me["is_guest"] is True and me["provider"] == "guest"
    assert client.get("/api/me").json()["id"] == me["id"]  # cookie-bound
    dash = client.get("/api/me/dashboard").json()
    assert dash["user"]["id"] == me["id"] and dash["graphs"] == [] and dash["stats"]["graphs"] == 0


def test_clarify_then_goal_writes_profile(client):
    q = client.post("/api/goals/clarify", json={"goal": "我想学会 Transformer", "background": "有一点基础"}).json()
    assert q["intro"] and 2 <= len(q["questions"]) <= 4
    assert q["questions"][0]["options"] and "id" in q["questions"][0]
    answers = [{"question": q["questions"][0]["question"], "answer": "我是计算机专业大三学生，会 Python，了解 PyTorch 基础"}]
    created = client.post("/api/goals", json={"goal": "我想学会 Transformer", "background": "有一点基础", "answers": answers}).json()
    graph = client.get(f"/api/graphs/{created['graph_id']}").json()
    assert graph["status"] == "ready"
    me = client.get("/api/me").json()
    assert graph["user_id"] == me["id"]
    dash = client.get("/api/me/dashboard").json()
    assert [g["id"] for g in dash["graphs"]] == [created["graph_id"]]
    kinds = {f["kind"] for f in dash["facts"]}
    texts = " ".join(f["text"] for f in dash["facts"])
    assert "background" in kinds and "计算机专业大三学生" in texts and "Python" in texts
    assert any(e["kind"] == "goal" for e in dash["events"])
    # my graph list is scoped to me
    assert [g["id"] for g in client.get("/api/graphs").json()] == [created["graph_id"]]


def test_quiz_and_chat_update_profile(client):
    created = client.post("/api/goals", json={"goal": "学习复变函数"}).json()
    graph = client.get(f"/api/graphs/{created['graph_id']}").json()
    node_id = next(n["id"] for n in graph["nodes"] if n["node_type"] == "concept")
    quiz = client.post(f"/api/nodes/{node_id}/quiz").json()
    answers = {q["id"]: 1 for q in quiz["questions"] if q["qtype"] == "single"}
    answers[quiz["questions"][-1]["id"]] = "我本科是数学专业，学过实分析，留数定理是把闭合曲线积分变成奇点留数之和。"
    client.post(f"/api/quizzes/{quiz['id']}/submit", json={"answers": answers})
    client.post(f"/api/nodes/{node_id}/chat", json={"question": "我了解 Java，但没学过 Python，怎么办？"})
    dash = client.get("/api/me/dashboard").json()
    kinds = [e["kind"] for e in dash["events"]]
    assert "quiz" in kinds and "chat" in kinds
    progress = [f for f in dash["facts"] if f["kind"] == "progress"]
    assert progress and "掌握度" in progress[0]["text"]
    assert any("Java" in f["text"] for f in dash["facts"])
    assert dash["stats"]["started_nodes"] >= 1


def test_manual_facts_crud(client):
    fact = client.post("/api/me/facts", json={"kind": "skill", "text": "会用 Git 和 Linux 命令行"}).json()
    assert fact["source"] == "manual"
    dup = client.post("/api/me/facts", json={"kind": "skill", "text": "会用 Git 和 Linux 命令行。"}).json()
    assert dup["id"] == fact["id"]  # de-duplicated
    assert client.delete(f"/api/me/facts/{fact['id']}").status_code == 204
    assert client.delete(f"/api/me/facts/{fact['id']}").status_code == 404


def test_attachment_upload_list_context_delete(client):
    content = "数据结构课程大纲\n第一章 线性表\n第二章 树与二叉树\n第三章 图\n我是软件工程专业学生".encode()
    r = client.post("/api/attachments", files={"file": ("大纲.txt", io.BytesIO(content), "text/plain")})
    assert r.status_code == 201, r.text
    att = r.json()
    assert att["has_text"] and att["filename"].endswith(".txt") and "线性表" in att["summary"]
    listed = client.get("/api/attachments").json()
    assert [a["id"] for a in listed] == [att["id"]]
    dl = client.get(f"/api/attachments/{att['id']}/download")
    assert dl.status_code == 200 and "第二章" in dl.text
    dash = client.get("/api/me/dashboard").json()
    assert any(e["kind"] == "upload" for e in dash["events"]) and dash["attachments"][0]["id"] == att["id"]
    # attachments feed the clarification + graph prompts (mock ignores content, but the plumbing must not fail)
    q = client.post("/api/goals/clarify", json={"goal": "期末复习数据结构", "attachment_ids": [att["id"]]}).json()
    assert q["questions"]
    created = client.post("/api/goals", json={"goal": "期末复习数据结构", "attachment_ids": [att["id"]]}).json()
    assert client.get(f"/api/graphs/{created['graph_id']}").json()["status"] == "ready"
    assert client.delete(f"/api/attachments/{att['id']}").status_code == 204
    assert client.get(f"/api/attachments/{att['id']}/download").status_code == 404


def test_pdf_and_docx_text_extraction():
    from app.services.attachments import extract_text

    assert extract_text("a.md", "# 标题\n正文".encode()) == "# 标题\n正文"
    assert extract_text("a.bin", b"\x00\x01") == ""
