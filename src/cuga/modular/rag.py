from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

from .memory import MemoryRecord, VectorMemory


@dataclass
class RagDocument:
    text: str
    path: str


@dataclass
class RagHit:
    text: str
    score: float


class RagLoader:
    def __init__(self, backend: Optional[str] = None) -> None:
        self.memory = VectorMemory(backend=backend or "local")

    def ingest(self, files: Iterable[Path]) -> int:
        added = 0
        for path in files:
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            self.memory.remember(text, metadata={"path": str(path)})
            added += 1
        return added


class RagRetriever:
    def __init__(self, backend: Optional[str] = None) -> None:
        self.memory = VectorMemory(backend=backend or "local")

    def query(self, query: str, top_k: int = 5) -> List[RagHit]:
        matches: List[MemoryRecord] = self.memory.search(query, top_k=top_k)
        return [RagHit(text=rec.text, score=1.0) for rec in matches]
