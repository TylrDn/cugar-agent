from __future__ import annotations

from .base import EmbeddedRecord, SearchHit, VectorBackend


class FaissBackend(VectorBackend):
    def __init__(self) -> None:
        self._index = None
        self._metadata: list[EmbeddedRecord] = []
        self._faiss = None
        self._np = None

    def connect(self) -> None:
        import importlib

        self._faiss = importlib.import_module("faiss")
        self._np = importlib.import_module("numpy")
        self._index = None

    def _ensure_index(self, dim: int) -> None:
        if self._index is None:
            self._index = self._faiss.IndexFlatL2(dim)

    def upsert(self, records: list[EmbeddedRecord]) -> None:
        if not records or self._faiss is None or self._np is None:
            return
        dim = len(records[0].embedding)
        self._ensure_index(dim)
        embeddings = self._np.stack(
            [self._np.array(rec.embedding, dtype="float32") for rec in records]
        )
        self._index.add(embeddings)
        self._metadata.extend(records)

    def search(self, query_vector: list[float], top_k: int) -> list[SearchHit]:
        if self._index is None or self._np is None:
            return []
        top_k = min(top_k, len(self._metadata))
        distances, indices = self._index.search(self._np.array(query_vector, dtype="float32")[None, :], top_k)
        hits: list[SearchHit] = []
        for dist, idx in zip(distances[0], indices[0]):
            record = self._metadata[int(idx)].record
            score = float(1.0 / (1.0 + dist))
            hits.append(SearchHit(text=record.text, metadata=record.metadata, score=score))
        return hits
