from __future__ import annotations

from typing import List

from cuga.modular.memory import VectorMemory
from cuga.modular.vector_backends.base import EmbeddedRecord, SearchHit


class SimpleVectorBackend:
    def __init__(self) -> None:
        self.records: List[EmbeddedRecord] = []

    def connect(self) -> None:
        return None

    def upsert(self, records: List[EmbeddedRecord]) -> None:
        self.records.extend(records)

    def search(self, query_vector: list[float], top_k: int) -> list[SearchHit]:
        hits: list[SearchHit] = []
        for rec in self.records:
            dot = sum(q * r for q, r in zip(query_vector, rec.embedding))
            norm = (sum(r * r for r in rec.embedding) ** 0.5) or 1e-8
            score = float(dot / norm)
            hits.append(SearchHit(text=rec.record.text, metadata=rec.record.metadata, score=score))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:top_k]


def test_vector_search_scores_rank_by_similarity() -> None:
    memory = VectorMemory(profile="p1", backend_name="faiss")
    memory.backend = SimpleVectorBackend()
    memory.remember("alpha beta gamma", metadata={"path": "a"})
    memory.remember("alpha beta", metadata={"path": "b"})
    memory.remember("delta epsilon", metadata={"path": "c"})

    hits = memory.search("alpha beta", top_k=2)
    assert hits[0].metadata["path"] == "b"
    assert hits[0].score >= hits[1].score
