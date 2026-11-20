"""FastAPI 入口：静态页面 + 聊天接口 + 健康检查 + 会话重置 + 用例沉淀。"""
import json
import re
import time
import uuid

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .agent_factory import build_agent
from .config import BASE_DIR, settings
from . import db, runtime
from .llm import LLMClient  # noqa: F401  保留以便测试/脚本直接引用
from .memory import SessionStore
from .schemas import (
    ChatRequest, ChatResponse, EvalCaseRequest, EvalCaseResponse,
    ModeRequest, ModeResponse,
)
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
agent = build_agent(memory)

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
        "vector_backend": KB.backend,
        "vector_embed": KB.mode,
        "agent_framework": settings.agent_framework if not runtime.is_mock() else "native",
        "session_store": "redis" if memory._redis is not None else "memory",
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


# ---- 评测用例库：把对话界面里聊过的问题沉淀成可回归的测试用例 ----
CASES_PATH = BASE_DIR / "eval" / "cases.json"


def _load_cases() -> list[dict]:
    try:
        data = json.loads(CASES_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _next_case_id(cases: list[dict]) -> str:
    nums = []
    for case in cases:
        cid = str(case.get("id", ""))
        m = re.match(r"^E(\d+)$", cid)
        if m:
            nums.append(int(m.group(1)))
    return f"E{max(nums) + 1:02d}" if nums else "E01"


@app.get("/api/eval/cases")
async def list_cases():
    cases = _load_cases()
    return {"total": len(cases), "cases": cases}


@app.post("/api/eval/cases", response_model=EvalCaseResponse)
async def save_case(request: EvalCaseRequest):
    cases = _load_cases()
    case_id = _next_case_id(cases)
    cases.append({
        "id": case_id,
        "category": request.category,
        "message": request.message.strip(),
        "expect_tool": request.expect_tool or None,
        "expect_keywords": request.expect_keywords,
        "note": request.note,
        "source": "ui",  # 标记来自对话界面沉淀
    })
    CASES_PATH.write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")
    return EvalCaseResponse(ok=True, id=case_id, total=len(cases), path="eval/cases.json")
