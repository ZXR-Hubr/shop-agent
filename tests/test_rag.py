import math

from app.rag import KnowledgeBase, _local_vector


def test_local_vector_is_normalized():
    vector = _local_vector("包邮")
    norm = math.sqrt(sum(value * value for value in vector))
    assert abs(norm - 1.0) < 1e-6


def test_knowledge_base_returns_relevant_doc():
    kb = KnowledgeBase()
    results = kb.search("发票怎么开", top_k=3)
    assert results
    assert any("发票" in item["title"] for item in results[:2])


def test_knowledge_base_scores_are_sorted():
    kb = KnowledgeBase()
    scores = [item["score"] for item in kb.search("保修多久", top_k=5)]
    assert scores == sorted(scores, reverse=True)
