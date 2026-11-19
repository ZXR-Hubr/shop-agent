"""MySQL 连接配置：从环境变量 / .env 读取，不硬编码密码。"""
import os
from dataclasses import dataclass

from .config import load_dotenv, BASE_DIR

load_dotenv(BASE_DIR / ".env")


def _flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class MysqlSettings:
    enabled: bool
    host: str
    port: int
    user: str
    password: str
    database: str
    charset: str


def load_mysql_settings() -> MysqlSettings:
    return MysqlSettings(
        enabled=_flag("MYSQL_ENABLED", default=False),
        host=os.getenv("MYSQL_HOST", "127.0.0.1").strip(),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root").strip(),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DATABASE", "xiaoman_shop").strip(),
        charset="utf8mb4",
    )


mysql_settings = load_mysql_settings()
