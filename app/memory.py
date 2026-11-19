"""会话记忆管理。

默认使用进程内字典；配置 REDIS_URL 后自动切换为 Redis，实现多进程共享。
只保存 user / assistant 的最终消息，工具调用的中间结果不落库。
"""
import json
import time
from typing import Any


class SessionStore:
    def __init__(self, ttl: int = 3600, max_history: int = 20, redis_url: str = ""):
        self.ttl = ttl
        self.max_history = max_history
        self._local: dict[str, dict[str, Any]] = {}
        self._redis = None
        if redis_url:
            try:
                import redis.asyncio as aioredis

                self._redis = aioredis.from_url(redis_url, decode_responses=True)
            except Exception:
                # 没装 redis 客户端时安静回退到内存，不影响主流程
                self._redis = None

    async def get(self, session_id: str) -> list[dict]:
        if self._redis is not None:
            raw = await self._redis.get(f"chat:{session_id}")
            return json.loads(raw) if raw else []

        item = self._local.get(session_id)
        if not item:
            return []
        if time.time() - item["updated"] > self.ttl:
            self._local.pop(session_id, None)
            return []
        return item["messages"]

    async def append(self, session_id: str, role: str, content: str) -> None:
        messages = await self.get(session_id)
        messages.append({"role": role, "content": content})
        # 只保留最近 N 条，避免上下文无限增长
        messages = messages[-self.max_history:]

        if self._redis is not None:
            await self._redis.set(
                f"chat:{session_id}",
                json.dumps(messages, ensure_ascii=False),
                ex=self.ttl,
            )
            return
        self._local[session_id] = {"messages": messages, "updated": time.time()}

    async def clear(self, session_id: str) -> None:
        if self._redis is not None:
            await self._redis.delete(f"chat:{session_id}")
        self._local.pop(session_id, None)
