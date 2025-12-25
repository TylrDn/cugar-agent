from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

from .memory import VectorMemory
from .vector_backends.base import SearchHit


@dataclass
class RagDocument:
    text: str
    path: str


@dataclass
class RagHit:
    text: str
    score: float
    metadata: dict


class RagLoader:
    def __init__(self, backend: Optional[str] = None, profile: str = "default") -> None:
        self.memory = VectorMemory(backend_name=backend or "local", profile=profile)
        self.memory.connect_backend()

    def ingest(self, files: Iterable[Path]) -> int:
        added = 0
        for path in files:
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            self.memory.remember(text, metadata={"path": str(path), "profile": self.memory.profile})
            added += 1
        return added


class RagRetriever:
    def __init__(self, backend: Optional[str] = None, profile: str = "default") -> None:
        self.memory = VectorMemory(backend_name=backend or "local", profile=profile)
        self.memory.connect_backend()

    def query(self, query: str, top_k: int = 5) -> List[RagHit]:
        matches: List[SearchHit] = self.memory.search(query, top_k=top_k)
        return [RagHit(text=hit.text, score=hit.score, metadata=hit.metadata) for hit in matches]
