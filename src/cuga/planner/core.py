from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from typing import Any, AsyncIterator, Callable, Dict, List

from cuga.observability import InMemoryTracer, propagate_trace
from cuga.sandbox.isolation import validate_tool_path


@dataclass
class PlanStep:
    tool: str
    params: Dict[str, Any]


class Planner:
    def __init__(self, tracer: InMemoryTracer | None = None) -> None:
        self.tracer = tracer or InMemoryTracer()

    async def plan(self, goal: str, metadata: Dict[str, Any] | None = None, stream_cb: Callable[[Dict[str, Any]], None] | None = None) -> List[PlanStep]:
        metadata = metadata or {}
        trace_id = metadata.get("trace_id") or str(uuid.uuid4())
        propagate_trace(trace_id)
        span = self.tracer.start_span("plan.create", goal=goal, trace_id=trace_id)
        steps = [PlanStep(tool="cuga.modular.tools.echo", params={"message": goal})]
        validate_tool_path(steps[0].tool)
        if stream_cb:
            stream_cb({"trace_id": trace_id, "event": "planned", "steps": len(steps)})
        span.end(steps=len(steps))
        await asyncio.sleep(0)
        return steps

    async def stream(self, goal: str) -> AsyncIterator[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        steps = await self.plan(goal, stream_cb=events.append)
        for event in events:
            yield event
        yield {"steps": [s.tool for s in steps]}
