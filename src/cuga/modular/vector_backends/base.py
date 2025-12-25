from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..types import MemoryRecord


@dataclass
class EmbeddedRecord:
    embedding: list[float]
    record: MemoryRecord


@dataclass
class SearchHit:
    text: str
    metadata: dict
    score: float


class VectorBackend(Protocol):
    def connect(self) -> None:
        ...

    def upsert(self, records: list[EmbeddedRecord]) -> None:
        ...

    def search(self, query_vector: list[float], top_k: int) -> list[SearchHit]:
        ...
