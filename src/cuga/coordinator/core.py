from __future__ import annotations

import asyncio
import threading
from typing import Any, AsyncIterator, Dict, Iterable, List

from cuga.observability import InMemoryTracer, propagate_trace


class Coordinator:
    def __init__(self, workers: Iterable[Any], tracer: InMemoryTracer | None = None) -> None:
        self.workers = list(workers)
        self._lock = threading.Lock()
        self._index = 0
        self.tracer = tracer or InMemoryTracer()

    def _next_worker(self) -> Any:
        with self._lock:
            worker = self.workers[self._index % len(self.workers)]
            self._index += 1
            return worker

    async def run(self, plan: List[Any], trace_id: str) -> AsyncIterator[Dict[str, Any]]:
        propagate_trace(trace_id)
        for step in plan:
            worker = self._next_worker()
            span = self.tracer.start_span("worker.dispatch", trace_id=trace_id, tool=step.tool)
            result = await worker.execute(step, trace_id=trace_id)
            span.end(status="ok")
            yield {"worker": worker.name, "result": result, "trace_id": trace_id}
            await asyncio.sleep(0)
