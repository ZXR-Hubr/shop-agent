from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["kb_size"] > 0


def test_chat_returns_reply_and_session():
    response = client.post("/api/chat", json={"message": "订单 SO20261114002 到哪了"})
    assert response.status_code == 200
    body = response.json()
    assert body["session_id"]
    assert "运输中" in body["reply"]
    assert body["tool_calls"][0]["name"] == "get_order"
    assert body["latency_ms"] >= 0


def test_chat_reuses_session():
    first = client.post("/api/chat", json={"message": "你好"}).json()
    second = client.post(
        "/api/chat",
        json={"session_id": first["session_id"], "message": "订单 SO20261114002 到哪了"},
    ).json()
    assert second["session_id"] == first["session_id"]


def test_reset_session():
    first = client.post("/api/chat", json={"message": "你好"}).json()
    response = client.post(f"/api/session/{first['session_id']}/reset")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_index_page():
    response = client.get("/")
    assert response.status_code == 200
    assert "小满" in response.text
