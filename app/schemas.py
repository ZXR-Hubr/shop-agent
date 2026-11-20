"""HTTP 请求 / 响应模型。"""
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str = Field(..., min_length=1, max_length=2000)


class ToolCallRecord(BaseModel):
    name: str
    arguments: dict
    result: dict


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    usage: dict = Field(default_factory=dict)
    latency_ms: int = 0


class ModeRequest(BaseModel):
    mode: str = Field(..., pattern="^(mock|api)$")


class ModeResponse(BaseModel):
    mode: str
    model: str
    changed: bool = True


class EvalCaseRequest(BaseModel):
    """从对话界面保存一条测试用例。"""
    message: str = Field(..., min_length=1, max_length=2000)
    expect_tool: str | None = None
    expect_keywords: list[str] = Field(default_factory=list)
    category: str = "功能"
    note: str = ""


class EvalCaseResponse(BaseModel):
    ok: bool
    id: str
    total: int
    path: str
