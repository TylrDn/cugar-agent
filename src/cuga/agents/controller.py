"""Controller orchestrating planner and executor layers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict

from .executor import ExecutionContext, ExecutionResult, Executor
from .planner import Planner, PlanningPreferences
from .registry import ToolRegistry


@dataclass
class Controller:
    planner: Planner
    executor: Executor
    registry: ToolRegistry

    audit_logger = logging.getLogger("cuga.audit")

    def run(
        self,
        goal: str,
        profile: str,
        *,
        metadata: Dict[str, Any] | None = None,
        preferences: PlanningPreferences | None = None,
    ) -> ExecutionResult:
        audit_entry = {
            "event": "controller.run",
            "profile": profile,
            "goal": goal,
            "policy": "allow",
        }
        audit_message = f"[audit] {audit_entry}"
        self.audit_logger.info(audit_message)

        sandboxed_registry = self.registry.sandbox(profile)
        plan_result = self.planner.plan(goal, sandboxed_registry, preferences=preferences)
        context = ExecutionContext(profile=profile, metadata=metadata)

        trace = [audit_message]
        trace.extend(plan_result.trace)

        return self.executor.execute_plan(plan_result.steps, sandboxed_registry, context, trace=trace)
