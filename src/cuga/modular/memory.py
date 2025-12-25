from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .embeddings.interface import Embedder
from .embeddings.hashing import HashingEmbedder
from .types import MemoryRecord
from .vector_backends.base import EmbeddedRecord, SearchHit, VectorBackend
from .vector_backends.chroma_backend import ChromaBackend
from .vector_backends.faiss_backend import FaissBackend
from .vector_backends.qdrant_backend import QdrantBackend

LOGGER = logging.getLogger(__name__)


_BACKEND_REGISTRY: Dict[str, type[VectorBackend]] = {
    "faiss": FaissBackend,
    "chroma": ChromaBackend,
    "qdrant": QdrantBackend,
}


@dataclass
class VectorMemory:
    profile: str = "default"
    backend_name: str = "local"
    embedder: Embedder = field(default_factory=HashingEmbedder)
    backend: Optional[VectorBackend] = None
    store: List[MemoryRecord] = field(default_factory=list)

    def connect_backend(self) -> None:
        if self.backend_name == "local":
            LOGGER.info("Using local memory backend", extra={"profile": self.profile})
            return
        backend_cls = _BACKEND_REGISTRY.get(self.backend_name)
        if backend_cls is None:
            raise RuntimeError(f"Unsupported backend {self.backend_name}")
        try:
            backend = backend_cls()
            backend.connect()
        except ImportError as exc:  # pragma: no cover - defensive
            raise RuntimeError(
                f"Backend {self.backend_name} is not installed. Install the appropriate client or use local fallback."
            ) from exc
        self.backend = backend
        LOGGER.info("Connected vector backend", extra={"backend": self.backend_name, "profile": self.profile})

    def remember(self, text: str, metadata: Optional[Dict[str, str]] = None) -> None:
        merged_metadata = {"profile": self.profile}
        if metadata:
            merged_metadata.update(metadata)
        record = MemoryRecord(text=text, metadata=merged_metadata)
        self.store.append(record)
        if self.backend_name != "local":
            if self.backend is None:
                self.connect_backend()
            if self.backend is None:
                return
            embedding = self.embedder.embed(text)
            self.backend.upsert([EmbeddedRecord(embedding=embedding, record=record)])

    def search(self, query: str, top_k: int = 3) -> List[SearchHit]:
        if self.backend is not None:
            query_vector = self.embedder.embed(query)
            return self.backend.search(query_vector, top_k)
        return self._local_search(query, top_k)

    def _local_search(self, query: str, top_k: int) -> List[SearchHit]:
        query_terms = self._normalize_words(query)
        if not query_terms:
            return []
        scored: List[SearchHit] = []
        for record in self.store:
            record_terms = self._normalize_words(record.text)
            overlap = len(query_terms & record_terms)
            if overlap == 0:
                continue
            score = overlap / max(len(query_terms), 1)
            scored.append(SearchHit(text=record.text, metadata=record.metadata, score=float(score)))
        scored.sort(key=lambda hit: hit.score, reverse=True)
        return scored[:top_k]

    @staticmethod
    def _normalize_words(text: str) -> set[str]:
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        return set(tokens)
