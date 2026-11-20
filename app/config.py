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
    # 向量库后端：local / pgvector / milvus
    vector_backend: str
    pg_dsn: str
    pg_host: str
    pg_port: int
    pg_user: str
    pg_password: str
    pg_database: str
    milvus_uri: str
    milvus_token: str
    milvus_collection: str
    # Agent 编排框架：native（手写循环）/ langchain
    agent_framework: str


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
        vector_backend=os.getenv("VECTOR_BACKEND", "local").strip().lower(),
        pg_dsn=os.getenv("PG_DSN", "").strip(),
        pg_host=os.getenv("PG_HOST", "127.0.0.1").strip(),
        pg_port=int(os.getenv("PG_PORT", "5432")),
        pg_user=os.getenv("PG_USER", "postgres").strip(),
        pg_password=os.getenv("PG_PASSWORD", "").strip(),
        pg_database=os.getenv("PG_DATABASE", "shop_agent").strip(),
        milvus_uri=os.getenv("MILVUS_URI", "http://127.0.0.1:19530").strip(),
        milvus_token=os.getenv("MILVUS_TOKEN", "").strip(),
        milvus_collection=os.getenv("MILVUS_COLLECTION", "shop_agent_kb").strip(),
        agent_framework=os.getenv("AGENT_FRAMEWORK", "native").strip().lower(),
    )


settings = load_settings()
