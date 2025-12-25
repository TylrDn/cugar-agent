from __future__ import annotations

import uuid

from .base import EmbeddedRecord, SearchHit, VectorBackend


class ChromaBackend(VectorBackend):
    def __init__(self) -> None:
        self._client = None
        self._collection = None

    def connect(self) -> None:
        import chromadb

        self._client = chromadb.Client()
        self._collection = self._client.get_or_create_collection("cuga_modular")

    def upsert(self, records: list[EmbeddedRecord]) -> None:
        if self._collection is None:
            return
        ids = [str(uuid.uuid4()) for _ in records]
        embeddings = [rec.embedding for rec in records]
        metadatas = [rec.record.metadata for rec in records]
        documents = [rec.record.text for rec in records]
        self._collection.upsert(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=documents)

    def search(self, query_vector: list[float], top_k: int) -> list[SearchHit]:
        if self._collection is None:
            return []
        results = self._collection.query(query_embeddings=[query_vector], n_results=top_k)
        hits: list[SearchHit] = []
        for doc, meta, distance in zip(
            results.get("documents", [[]])[0],
            results.get("metadatas", [[]])[0],
            results.get("distances", [[]])[0],
        ):
            score = float(1.0 / (1.0 + distance))
            hits.append(SearchHit(text=doc, metadata=meta or {}, score=score))
        return hits
