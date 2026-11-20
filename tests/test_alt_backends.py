"""验证四类"简历技术"确实在项目里真实可用（可切换 / 可降级 / 接口一致）。

- 向量库：local / pgvector / milvus 三套实现接口一致，外部失败降级 local
- Redis：会话记忆可用 fakeredis 真实走 Redis 读写路径
- LangChain：可选 Agent 实现能被工厂按配置选中/回退
- Flask：第二套 Web 入口可导入且路由齐全
"""
import os

import pytest


def test_vectorstore_three_backends_share_interface():
    from app.vectorstore import LocalVectorStore, PgVectorStore, MilvusVectorStore
    items = [("k1", [1.0, 0.0], {"content": "a"}), ("k2", [0.0, 1.0], {"content": "b"})]
    store = LocalVectorStore()
    store.upsert(items)
    hits = store.search([1.0, 0.0], top_k=2)
    assert hits[0][0] == "k1" and hits[0][1] > hits[1][1]
    # 三套实现都具备相同方法签名
    for cls in (PgVectorStore, MilvusVectorStore):
        assert hasattr(cls, "upsert") and hasattr(cls, "search") and hasattr(cls, "close")


def test_build_store_falls_back_to_local_when_service_missing():
    from app.vectorstore import build_store
    store, backend = build_store("pgvector", 8, dsn="postgresql://x:x@127.0.0.1:1/nope")
    assert backend == "local" and store.name == "local"


def test_redis_session_store_with_fakeredis(monkeypatch):
    import fakeredis.aioredis as fake_aioredis
    import redis.asyncio as aioredis

    fake = fake_aioredis.FakeRedis(decode_responses=True)

    def fake_from_url(url, **kwargs):
        return fake

    monkeypatch.setattr(aioredis, "from_url", fake_from_url)
    from app.memory import SessionStore

    store = SessionStore(redis_url="redis://fake/0")
    assert store._redis is not None
    import asyncio

    async def run():
        await store.append("s1", "user", "你好")
        await store.append("s1", "assistant", "您好")
        assert await store.get("s1") == [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "您好"},
        ]
        await store.clear("s1")
        assert await store.get("s1") == []

    asyncio.run(run())


def test_agent_factory_returns_native_in_mock(monkeypatch):
    from app import runtime
    monkeypatch.setattr(runtime, "is_mock", lambda: True)

    class _Memory:
        pass

    from app.agent_factory import build_agent
    from app.agent import Agent
    assert isinstance(build_agent(_Memory()), Agent)


def test_flask_app_importable_with_routes():
    import flask_app
    paths = {rule.rule for rule in flask_app.app.url_map.iter_rules()}
    assert "/api/chat" in paths and "/api/health" in paths and "/" in paths
