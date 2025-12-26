from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Tuple


class VectorMemory:
    def __init__(self, ttl_seconds: int = 60, max_items: int = 100) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_items = max_items
        self._items: List[Tuple[float, Dict[str, Any]]] = []
        self._lock = asyncio.Lock()

    async def batch_upsert(self, items: List[Dict[str, Any]]) -> None:
        async with self._lock:
            now = time.time()
            for item in items:
                self._items.append((now, item))
            self._evict(now)

    async def similarity_search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        async with self._lock:
            now = time.time()
            self._evict(now)
            return [item for _, item in list(self._items)[:k]]

    def _evict(self, now: float) -> None:
        self._items = [(ts, item) for ts, item in self._items if now - ts <= self.ttl_seconds]
        if len(self._items) > self.max_items:
            self._items = self._items[-self.max_items :]
