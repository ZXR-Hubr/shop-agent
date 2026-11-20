"""RAG：把知识库文档转成向量，按余弦相似度召回 Top-K。

默认使用内置的本地向量化（字符二元组哈希），零依赖、离线可跑。
配置 EMBED_MODEL 后会自动改用远程 Embedding API，失败时静默回退。
生产环境可以把 KnowledgeBase 的存储换成 pgvector / Milvus，接口保持不变。
"""
import hashlib
import json
import math
from pathlib import Path

import httpx

from . import db
from .config import BASE_DIR, settings
from .vectorstore import build_store

DIM = 512


def _local_vector(text: str) -> list[float]:
    """轻量本地向量化：字符 bigram 哈希 + 符号散列，再做 L2 归一化。"""
    text = text.lower()
    vec = [0.0] * DIM
    tokens = [text[i:i + 2] for i in range(len(text) - 1)] or ([text] if text else [])
    for token in tokens:
        h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
        vec[h % DIM] += 1.0 if (h >> 8) & 1 else -1.0
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def embed_texts(texts: list[str]) -> tuple[list[list[float]], str]:
    if settings.embed_model and settings.llm_api_key and not settings.llm_mock:
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(
                    f"{settings.llm_base_url}/embeddings",
                    headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                    json={"model": settings.embed_model, "input": texts},
                )
                resp.raise_for_status()
                vectors = [item["embedding"] for item in resp.json()["data"]]
            return vectors, "api"
        except Exception:
            pass
    return [_local_vector(t) for t in texts], "local"


def _cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


class KnowledgeBase:
    """知识库 + 向量索引。启动时一次性构建，查询时做余弦相似度排序。"""

    def __init__(self, path: Path | None = None):
        # 优先从 MySQL 加载知识库（tags 是逗号分隔字符串，转回列表）
        rows = db.fetch_all("SELECT id,title,content,tags FROM kb_articles ORDER BY id")
        if rows:
            self.docs = [
                {
                    "id": r["id"],
                    "title": r["title"],
                    "content": r["content"],
                    "tags": [t for t in (r.get("tags") or "").split(",") if t],
                }
                for r in rows
            ]
            self.source = "mysql"
        else:
            path = path or BASE_DIR / "data" / "kb.json"
            self.docs = json.loads(Path(path).read_text(encoding="utf-8"))
            self.source = "json"
        texts = [f"{doc['title']}\n{doc['content']}" for doc in self.docs]
        self.vectors, self.mode = embed_texts(texts)

        # 按配置构建向量存储后端（local / pgvector / milvus），失败自动降级
        self.store, self.backend = build_store(
            settings.vector_backend,
            len(self.vectors[0]) if self.vectors else DIM,
            dsn=settings.pg_dsn,
            host=settings.pg_host,
            port=settings.pg_port,
            user=settings.pg_user,
            password=settings.pg_password,
            database=settings.pg_database,
            milvus_uri=settings.milvus_uri,
            milvus_token=settings.milvus_token,
            milvus_collection=settings.milvus_collection,
        )
        payloads = [{"content": doc["content"], "tags": ",".join(doc.get("tags") or [])} for doc in self.docs]
        self.store.upsert([
            (doc["id"], vec, payload)
            for doc, vec, payload in zip(self.docs, self.vectors, payloads)
        ])

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        query_vec = embed_texts([query])[0][0]
        hits = self.store.search(query_vec, top_k)
        by_id = {doc["id"]: doc for doc in self.docs}
        results = []
        for doc_id, score in hits:
            doc = by_id.get(doc_id)
            if doc is None:
                continue
            results.append({
                "score": round(score, 4),
                "id": doc["id"],
                "title": doc["title"],
                "content": doc["content"],
            })
            if len(results) >= top_k:
                break
        return results
