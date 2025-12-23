from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from typing import Dict, Optional, Tuple

from cuga.mcp.errors import CallTimeout, CircuitOpen, ToolUnavailable
from cuga.mcp.interfaces import ToolRequest, ToolResponse, ToolSpec
from cuga.mcp.registry import MCPRegistry
from cuga.mcp.runners.subprocess_stdio import SubprocessStdioRunner
from cuga.mcp.telemetry.logging import setup_json_logging
from cuga.mcp.telemetry.metrics import metrics

LOGGER = setup_json_logging()


class CircuitState:
    def __init__(self, threshold: int = 3, cooldown_s: float = 10.0) -> None:
        self.threshold = threshold
        self.cooldown_s = cooldown_s
        self.failures = 0
        self.open_until = 0.0

    def record_success(self) -> None:
        self.failures = 0
        self.open_until = 0.0

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures >= self.threshold:
            self.open_until = time.time() + self.cooldown_s

    def allow(self) -> bool:
        if self.open_until and time.time() < self.open_until:
            return False
        return True


class LifecycleManager:
    def __init__(self, registry: Optional[MCPRegistry] = None) -> None:
        self.registry = registry or MCPRegistry()
        self.runners: Dict[Tuple[str, str], SubprocessStdioRunner] = {}
        self.circuits: Dict[str, CircuitState] = defaultdict(CircuitState)
        self.pool: Dict[str, deque[SubprocessStdioRunner]] = defaultdict(deque)

    def _runner_key(self, spec: ToolSpec) -> Tuple[str, str]:
        return (spec.alias, spec.transport)

    async def ensure_runner(self, spec: ToolSpec) -> SubprocessStdioRunner:
        key = self._runner_key(spec)
        if key in self.runners and self.runners[key].is_healthy():
            return self.runners[key]
        runner = SubprocessStdioRunner(
            command=spec.command or "python",
            args=spec.args,
            env=spec.env,
            working_dir=spec.working_dir,
        )
        await runner.start()
        self.runners[key] = runner
        return runner

    async def stop_runner(self, alias: str, transport: str = "stdio") -> None:
        key = (alias, transport)
        runner = self.runners.pop(key, None)
        if runner:
            await runner.stop()

    async def call(self, alias: str, request: ToolRequest) -> ToolResponse:
        spec = self.registry.get(alias)
        circuit = self.circuits[alias]
        if not circuit.allow():
            raise CircuitOpen(f"Circuit open for {alias}")
        runner = await self.ensure_runner(spec)
        metrics.counter("mcp.calls").inc()
        stop_timer = metrics.time_block("mcp.latency_ms")
        try:
            payload = {"method": request.method, "params": request.params}
            raw = await runner.call_with_retry(payload, timeout=request.timeout_s or spec.timeout_s)
            stop_timer()
            circuit.record_success()
            return ToolResponse(ok=True, result=raw.get("result"), metrics={"transport": spec.transport})
        except (CallTimeout, ToolUnavailable) as exc:
            circuit.record_failure()
            stop_timer()
            metrics.counter("mcp.errors").inc()
            return ToolResponse(ok=False, error=str(exc), metrics={"transport": spec.transport})

    async def stop_all(self) -> None:
        await asyncio.gather(*(runner.stop() for runner in list(self.runners.values())))
        self.runners.clear()

