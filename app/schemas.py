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
