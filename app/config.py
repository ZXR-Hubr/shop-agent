"""集中管理配置：所有可调参数都来自环境变量 / .env 文件。"""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    embed_model: str
    llm_mock: bool
    redis_url: str
    session_ttl: int
    max_history: int
    max_tool_rounds: int
    request_timeout: float
    temperature: float


def load_settings() -> Settings:
    api_key = os.getenv("LLM_API_KEY", "").strip()
    return Settings(
        llm_api_key=api_key,
        llm_base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
        llm_model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        embed_model=os.getenv("EMBED_MODEL", "").strip(),
        # 显式开启 Mock，或者没有配置 Key 时，自动进入 Mock 模式
        llm_mock=_flag("LLM_MOCK", default=not api_key),
        redis_url=os.getenv("REDIS_URL", "").strip(),
        session_ttl=int(os.getenv("SESSION_TTL", "3600")),
        max_history=int(os.getenv("MAX_HISTORY", "20")),
        max_tool_rounds=int(os.getenv("MAX_TOOL_ROUNDS", "5")),
        request_timeout=float(os.getenv("REQUEST_TIMEOUT", "60")),
        temperature=float(os.getenv("TEMPERATURE", "0.3")),
    )


settings = load_settings()
