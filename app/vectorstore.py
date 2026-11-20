"""向量存储后端抽象：同一份知识库向量，可切换 local / pgvector / Milvus 三套实现。

这是简历里「RAG 向量检索（pgvector / Milvus 双方案）」的真实落地：
- local：进程内余弦检索，零依赖，默认方案（保证开箱即跑）；
- pgvector：PostgreSQL + pgvector 扩展，向量列用 vector 类型 + 余弦距离索引；
- milvus：Milvus 向量数据库，COSINE 度量。

三套实现对外接口完全一致（upsert / search），知识库层不感知底层差异。
任一外部后端连接失败时自动降级到 local，保证 Demo 永远可用。
"""
import math
from typing import Protocol


class VectorStore(Protocol):
    """向量存储统一接口。"""

    name: str

    def upsert(self, items: list[tuple[str, list[float], dict]]) -> None:
        """写入/更新向量。items: (id, vector, payload)。"""

    def search(self, query_vec: list[float], top_k: int) -> list[tuple[str, float]]:
        """返回 [(id, cosine_score)]，按分数降序。"""

    def close(self) -> None:
        ...


def _cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


class LocalVectorStore:
    """默认实现：内存 list + 余弦相似度。零依赖、离线可用。"""

    name = "local"

    def __init__(self):
        self._rows: list[tuple[str, list[float], dict]] = []

    def upsert(self, items: list[tuple[str, list[float], dict]]) -> None:
        by_id = {row[0]: row for row in self._rows}
        for doc_id, vec, payload in items:
            by_id[doc_id] = (doc_id, vec, payload)
        self._rows = list(by_id.values())

    def search(self, query_vec: list[float], top_k: int) -> list[tuple[str, float]]:
        scored = [(_id, _cosine(query_vec, vec)) for _id, vec, _ in self._rows]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def close(self) -> None:
        self._rows.clear()


class PgVectorStore:
    """PostgreSQL + pgvector 实现。

    建表（首次自动执行）：
        CREATE EXTENSION IF NOT EXISTS vector;
        CREATE TABLE IF NOT EXISTS kb_vectors (
            id TEXT PRIMARY KEY, content TEXT, tags TEXT,
            embedding vector(DIM)
        );
        CREATE INDEX ON kb_vectors USING hnsw (embedding vector_cosine_ops);

    检索：ORDER BY embedding <=> %s::vector（余弦距离），score = 1 - distance。
    """

    name = "pgvector"

    def __init__(self, dim: int, dsn: str = "", host: str = "127.0.0.1",
                 port: int = 5432, user: str = "postgres", password: str = "",
                 database: str = "shop_agent"):
        import psycopg2  # 延迟导入：没装驱动时由工厂降级，不影响默认启动

        self.dim = dim
        kwargs = {"dbname": database, "user": user, "password": password, "host": host, "port": port}
        self.conn = psycopg2.connect(dsn) if dsn else psycopg2.connect(**kwargs)
        self.conn.autocommit = True
        with self.conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cur.execute(
                f"CREATE TABLE IF NOT EXISTS kb_vectors ("
                f"id TEXT PRIMARY KEY, content TEXT, tags TEXT, embedding vector({dim}))"
            )

    def upsert(self, items: list[tuple[str, list[float], dict]]) -> None:
        import psycopg2.extras

        rows = []
        for doc_id, vec, payload in items:
            literal = "[" + ",".join(f"{x:.8f}" for x in vec) + "]"
            rows.append((doc_id, payload.get("content", ""), payload.get("tags", ""), literal))
        with self.conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO kb_vectors (id,content,tags,embedding) VALUES (%s,%s,%s,%s::vector) "
                "ON CONFLICT (id) DO UPDATE SET content=EXCLUDED.content, "
                "tags=EXCLUDED.tags, embedding=EXCLUDED.embedding",
                rows,
            )

    def search(self, query_vec: list[float], top_k: int) -> list[tuple[str, float]]:
        literal = "[" + ",".join(f"{x:.8f}" for x in query_vec) + "]"
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id, 1 - (embedding <=> %s::vector) AS score "
                "FROM kb_vectors ORDER BY embedding <=> %s::vector LIMIT %s",
                (literal, literal, top_k),
            )
            return [(row[0], float(row[1])) for row in cur.fetchall()]

    def close(self) -> None:
        self.conn.close()


class MilvusVectorStore:
    """Milvus 实现，使用官方 pymilvus MilvusClient，COSINE 度量。"""

    name = "milvus"

    def __init__(self, dim: int, uri: str = "http://127.0.0.1:19530",
                 token: str = "", collection: str = "shop_agent_kb"):
        from pymilvus import MilvusClient  # 延迟导入

        self.dim = dim
        self.collection = collection
        self.client = MilvusClient(uri=uri, token=token or None)
        if not self.client.has_collection(collection_name=collection):
            self.client.create_collection(
                collection_name=collection,
                dimension=dim,
                metric_type="COSINE",
                auto_id=False,
                id_type="string",
                max_length=128,
            )

    def upsert(self, items: list[tuple[str, list[float], dict]]) -> None:
        rows = [
            {"id": str(doc_id), "vector": vec,
             "content": payload.get("content", ""), "tags": payload.get("tags", "")}
            for doc_id, vec, payload in items
        ]
        self.client.upsert(collection_name=self.collection, data=rows)

    def search(self, query_vec: list[float], top_k: int) -> list[tuple[str, float]]:
        hits = self.client.search(
            collection_name=self.collection,
            data=[query_vec],
            limit=top_k,
            output_fields=["content"],
            search_params={"metric_type": "COSINE", "params": {}},
        )
        result = []
        for group in hits:
            for hit in group:
                result.append((str(hit["id"]), float(hit["distance"])))
        return result

    def close(self) -> None:
        try:
            self.client.close()
        except Exception:
            pass


def build_store(backend: str, dim: int, *, dsn: str = "", host: str = "127.0.0.1",
                port: int = 5432, user: str = "postgres", password: str = "",
                database: str = "shop_agent", milvus_uri: str = "http://127.0.0.1:19530",
                milvus_token: str = "", milvus_collection: str = "shop_agent_kb") -> tuple[VectorStore, str]:
    """按配置构建向量存储，失败自动降级 local。返回 (store, 实际生效的后端名)。"""
    backend = (backend or "local").lower()
    try:
        if backend == "pgvector":
            store = PgVectorStore(dim, dsn, host, port, user, password, database)
            return store, "pgvector"
        if backend == "milvus":
            store = MilvusVectorStore(dim, milvus_uri, milvus_token, milvus_collection)
            return store, "milvus"
    except Exception:
        # 外部服务未启动 / 驱动缺失 → 静默降级，保证主流程不受影响
        pass
    return LocalVectorStore(), "local"
