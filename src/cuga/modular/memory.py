from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class MemoryRecord:
    text: str
    metadata: Dict[str, str]


@dataclass
class VectorMemory:
    profile: str = "default"
    backend: str = "local"
    store: List[MemoryRecord] = field(default_factory=list)

    def remember(self, text: str, metadata: Optional[Dict[str, str]] = None) -> None:
        self.store.append(MemoryRecord(text=text, metadata=metadata or {"profile": self.profile}))

    def search(self, query: str, top_k: int = 3) -> List[MemoryRecord]:
        matches = [rec for rec in self.store if query.lower() in rec.text.lower()]
        return matches[:top_k]

    def connect_backend(self) -> None:
        if self.backend == "local":
            return
        import importlib

        module_name = self._backend_module
        if not module_name:
            raise RuntimeError(
                f"Backend {self.backend} is not installed. Install the appropriate client or use local fallback."
            )
        if importlib.util.find_spec(module_name) is None:  # type: ignore[attr-defined]
            raise RuntimeError(
                f"Backend {self.backend} is not installed. Install the appropriate client or use local fallback."
            )
        importlib.import_module(module_name)

    @property
    def _backend_module(self) -> str:
        return {
            "chroma": "chromadb",
            "qdrant": "qdrant_client",
            "weaviate": "weaviate_client",
            "milvus": "pymilvus",
        }.get(self.backend, "")
