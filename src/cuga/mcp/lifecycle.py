from __future__ import annotations

# REVIEW-FIX: Circuit breaker accounting, allowlist pre-flight, and consistent error handling.

import asyncio
import time
from collections import defaultdict, deque
from typing import Dict, Optional, Tuple

from cuga.mcp.errors import CallTimeout, StartupError, ToolUnavailable
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
        if spec.transport != "stdio":
            raise ToolUnavailable(f"Unsupported transport: {spec.transport}")
        if key in self.runners and self.runners[key].is_healthy():
            return self.runners[key]
        runner = SubprocessStdioRunner(
            command=spec.command or "python",
            args=spec.args,
            env=spec.env,
            working_dir=spec.working_dir,
            allowed_commands=self.registry.config.allow_commands,
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
        metrics.counter("mcp.calls").inc()
        circuit = self.circuits[alias]
        if not circuit.allow():
            return ToolResponse(ok=False, error="circuit open", metrics={"transport": spec.transport})
        try:
            runner = await self.ensure_runner(spec)
        except ToolUnavailable as exc:
            circuit.record_failure()
            metrics.counter("mcp.errors", {"kind": "unavailable"}).inc()
            return ToolResponse(ok=False, error=str(exc), metrics={"transport": spec.transport})
        except StartupError as exc:
            circuit.record_failure()
            metrics.counter("mcp.errors", {"kind": "startup"}).inc()
            return ToolResponse(ok=False, error=str(exc), metrics={"transport": spec.transport})
        stop_timer = metrics.time_block("mcp.latency_ms")
        try:
            payload = {"method": request.method, "params": request.params}
            raw = await runner.call_with_retry(payload, timeout=request.timeout_s or spec.timeout_s)
            circuit.record_success()
            return ToolResponse(ok=True, result=raw.get("result"), metrics={"transport": spec.transport})
        except CallTimeout as exc:
            circuit.record_failure()
            metrics.counter("mcp.errors", {"kind": "timeout"}).inc()
            return ToolResponse(ok=False, error=str(exc), metrics={"transport": spec.transport})
        except StartupError as exc:
            circuit.record_failure()
            metrics.counter("mcp.errors", {"kind": "startup"}).inc()
            return ToolResponse(ok=False, error=str(exc), metrics={"transport": spec.transport})
        except ToolUnavailable as exc:
            circuit.record_failure()
            metrics.counter("mcp.errors", {"kind": "unavailable"}).inc()
            return ToolResponse(ok=False, error=str(exc), metrics={"transport": spec.transport})
        except Exception:  # REVIEW-FIX: keep callers stable by returning error
            circuit.record_failure()
            metrics.counter("mcp.errors", {"kind": "unexpected"}).inc()
            LOGGER.exception("Unexpected MCP failure", extra={"alias": alias})
            return ToolResponse(ok=False, error="unexpected error", metrics={"transport": spec.transport})
        finally:
            stop_timer()

    async def stop_all(self) -> None:
        await asyncio.gather(*(runner.stop() for runner in list(self.runners.values())))
        self.runners.clear()

