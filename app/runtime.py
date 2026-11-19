"""运行时可变状态：支持 Mock / API 模式热切换，无需重启服务。

默认值来自 .env 的 LLM_MOCK；启动后可通过 POST /api/mode 在线切换。
这样线上演示时，在网页点一下开关就能切换模式，不用重新部署。
"""
import threading

from .config import settings

_lock = threading.Lock()
_mode = "mock" if settings.llm_mock else "api"


def get_mode() -> str:
    with _lock:
        return _mode


def is_mock() -> bool:
    return get_mode() == "mock"


def set_mode(mode: str) -> str:
    global _mode
    mode = (mode or "").strip().lower()
    if mode not in ("mock", "api"):
        raise ValueError("mode 只能是 'mock' 或 'api'")
    if mode == "api" and not settings.llm_api_key:
        raise ValueError("未配置 API Key，无法切换到 API 模式，请先在 .env 填入 Key")
    with _lock:
        _mode = mode
    return _mode
