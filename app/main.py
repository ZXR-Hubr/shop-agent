"""FastAPI 入口：静态页面 + 聊天接口 + 健康检查 + 会话重置。"""
import time
import uuid

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .agent import Agent
from .config import BASE_DIR, settings
from . import db, runtime
from .llm import LLMClient
from .memory import SessionStore
from .schemas import ChatRequest, ChatResponse, ModeRequest, ModeResponse
from .tools import KB

app = FastAPI(
    title="电商智能客服 Agent",
    version="1.0.0",
    description="基于 LLM + Function Calling + RAG 的智能客服示例项目",
)

memory = SessionStore(
    ttl=settings.session_ttl,
    max_history=settings.max_history,
    redis_url=settings.redis_url,
)
agent = Agent(LLMClient(), memory)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "mode": runtime.get_mode(),
        "model": "mock" if runtime.is_mock() else settings.llm_model,
        "vector_backend": KB.mode,
        "kb_size": len(KB.docs),
        "data_source": "mysql" if KB.source == "mysql" else "json",
        "mysql_connected": db.ping(),
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    session_id = request.session_id or uuid.uuid4().hex
    started = time.perf_counter()
    result = await agent.chat(session_id, request.message.strip())
    latency_ms = int((time.perf_counter() - started) * 1000)
    return ChatResponse(
        session_id=session_id,
        reply=result["reply"],
        tool_calls=result["tool_calls"],
        usage=result["usage"],
        latency_ms=latency_ms,
    )


@app.post("/api/session/{session_id}/reset")
async def reset_session(session_id: str):
    await memory.clear(session_id)
    return {"ok": True, "session_id": session_id}


@app.get("/api/mode", response_model=ModeResponse)
async def get_mode():
    mode = runtime.get_mode()
    return ModeResponse(
        mode=mode,
        model="mock" if mode == "mock" else settings.llm_model,
        changed=False,
    )


@app.post("/api/mode", response_model=ModeResponse)
async def switch_mode(request: ModeRequest):
    try:
        mode = runtime.set_mode(request.mode)
    except ValueError as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=str(exc))
    return ModeResponse(
        mode=mode,
        model="mock" if mode == "mock" else settings.llm_model,
        changed=True,
    )
