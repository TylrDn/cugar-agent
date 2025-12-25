from __future__ import annotations

import uuid

from .base import EmbeddedRecord, SearchHit, VectorBackend


class QdrantBackend(VectorBackend):
    def __init__(self) -> None:
        self._client = None
        self._collection_name = "cuga_modular"

    def connect(self) -> None:
        from qdrant_client import QdrantClient, models

        self._models = models
        self._client = QdrantClient(location=":memory:")
        try:
            self._client.get_collection(self._collection_name)
        except Exception:
            self._client.create_collection(
                collection_name=self._collection_name,
                vectors_config=self._models.VectorParams(size=64, distance=self._models.Distance.COSINE),
            )

    def upsert(self, records: list[EmbeddedRecord]) -> None:
        if self._client is None:
            return
        payload = []
        for rec in records:
            payload.append(
                self._models.PointStruct(
                    id=str(uuid.uuid4()),
                    vector=rec.embedding,
                    payload={**rec.record.metadata, "text": rec.record.text},
                )
            )
        self._client.upsert(collection_name=self._collection_name, points=payload)

    def search(self, query_vector: list[float], top_k: int) -> list[SearchHit]:
        if self._client is None:
            return []
        results = self._client.search(
            collection_name=self._collection_name,
            query_vector=query_vector,
            limit=top_k,
        )
        hits: list[SearchHit] = []
        for point in results:
            score = float(point.score)
            metadata = dict(point.payload or {})
            text = metadata.get("text", "")
            hits.append(SearchHit(text=text, metadata=metadata, score=score))
        return hits
