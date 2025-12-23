"""Controller orchestrating planner and executor layers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from .executor import ExecutionContext, ExecutionResult, Executor
from .planner import Planner
from .registry import ToolRegistry


@dataclass
class Controller:
    planner: Planner
    executor: Executor
    registry: ToolRegistry

    def run(self, goal: str, profile: str, *, metadata: Dict[str, Any] | None = None) -> ExecutionResult:
        sandboxed_registry = self.registry.sandbox(profile)
        plan = self.planner.plan(goal, sandboxed_registry)
        context = ExecutionContext(profile=profile, metadata=metadata)
        return self.executor.execute_plan(plan, sandboxed_registry, context)
