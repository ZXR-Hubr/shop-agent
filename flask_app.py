"""Flask 版 Web 入口（与 FastAPI 版并存的第二套接口实现）。

简历里写「基于 FastAPI/Flask 封装后端服务接口」——本项目两个入口都真实提供：
- app/main.py：FastAPI 版（默认），自动交互文档 /docs；
- flask_app.py：Flask 版，用同一套 Agent / 向量库 / 数据源，接口保持一致。

启动：python flask_app.py  → http://127.0.0.1:8001
切换框架只改启动命令，业务逻辑零改动，体现「接口层与业务层解耦」。
"""
import asyncio
import time
import uuid

from flask import Flask, jsonify, request, send_from_directory

from app.agent_factory import build_agent
from app.config import BASE_DIR, settings
from app.memory import SessionStore

app = Flask(__name__, static_folder=None)
memory = SessionStore(
    ttl=settings.session_ttl,
    max_history=settings.max_history,
    redis_url=settings.redis_url,
)
agent = build_agent(memory)


@app.route("/")
def index():
    return send_from_directory(BASE_DIR / "static", "index.html")


@app.route("/api/health")
def health():
    from app.tools import KB
    from app import db, runtime
    return jsonify({
        "status": "ok",
        "framework": "flask",
        "mode": runtime.get_mode(),
        "vector_backend": KB.backend,
        "kb_size": len(KB.docs),
        "data_source": "mysql" if KB.source == "mysql" else "json",
        "mysql_connected": db.ping(),
    })


@app.route("/api/chat", methods=["POST"])
def chat():
    payload = request.get_json(force=True) or {}
    message = (payload.get("message") or "").strip()
    if not message:
        return jsonify({"error": "message 不能为空"}), 400
    session_id = payload.get("session_id") or uuid.uuid4().hex
    started = time.perf_counter()
    result = asyncio.run(agent.chat(session_id, message))
    return jsonify({
        "session_id": session_id,
        "reply": result["reply"],
        "tool_calls": result["tool_calls"],
        "usage": result["usage"],
        "latency_ms": int((time.perf_counter() - started) * 1000),
    })


@app.route("/api/session/<session_id>/reset", methods=["POST"])
def reset_session(session_id: str):
    asyncio.run(memory.clear(session_id))
    return jsonify({"ok": True, "session_id": session_id})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8001, debug=False)
