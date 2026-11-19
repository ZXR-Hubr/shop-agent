"""MySQL 数据访问层。

设计要点：
- 通过 MYSQL_ENABLED 开关控制；关闭或连接失败时，调用方自动回退到本地 JSON，
  保证 Mock 模式、单元测试、没有 MySQL 的机器都能照常跑。
- 连接按需创建、用完即关（demo 场景足够，避免长连接失效）。
- 把 Decimal / datetime 转成可 JSON 序列化的原生类型，方便直接返回给前端。
"""
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal

import pymysql

from .mysql_config import mysql_settings


def _jsonable(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat(sep=" ")[:19]
    return value


def _clean(row: dict) -> dict:
    return {k: _jsonable(v) for k, v in row.items()}


@contextmanager
def get_connection(database: str | None = None):
    """按需建立连接；MySQL 未启用时抛出 RuntimeError 由调用方回退。"""
    if not mysql_settings.enabled:
        raise RuntimeError("MySQL 未启用")
    conn = pymysql.connect(
        host=mysql_settings.host,
        port=mysql_settings.port,
        user=mysql_settings.user,
        password=mysql_settings.password,
        database=database or mysql_settings.database,
        charset=mysql_settings.charset,
        connect_timeout=5,
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        yield conn
    finally:
        conn.close()


def fetch_all(sql: str, params: tuple = ()) -> list[dict] | None:
    """返回全部行；MySQL 不可用返回 None（区别于「查到 0 行」的空列表）。"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return [_clean(r) for r in cur.fetchall()]
    except Exception:
        return None


def fetch_one(sql: str, params: tuple = ()) -> dict | None:
    rows = fetch_all(sql, params)
    if rows is None:
        return None
    return rows[0] if rows else {}


def execute(sql: str, params: tuple = ()) -> int | None:
    """执行写操作，返回影响行数；MySQL 不可用返回 None。"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                return cur.execute(sql, params)
    except Exception:
        return None


def ping() -> bool:
    """检测 MySQL 是否真正可连（开关开启且服务可用）。"""
    if not mysql_settings.enabled:
        return False
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                return cur.fetchone() is not None
    except Exception:
        return False
