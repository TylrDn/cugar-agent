"""Controller orchestrating planner and executor layers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

from .executor import ExecutionContext, ExecutionResult, Executor
from .policy import PolicyEnforcer
from .planner import Planner, PlanningPreferences
from .registry import ToolRegistry


@dataclass
class Controller:
    planner: Planner
    executor: Executor
    registry: ToolRegistry
    policy_enforcer: PolicyEnforcer = field(default_factory=PolicyEnforcer)

    def __post_init__(self) -> None:
        if getattr(self.executor, "policy_enforcer", None) is None:
            self.executor.policy_enforcer = self.policy_enforcer

    def run(
        self,
        goal: str,
        profile: str,
        *,
        metadata: Dict[str, Any] | None = None,
        preferences: PlanningPreferences | None = None,
    ) -> ExecutionResult:
        sandboxed_registry = self.registry.sandbox(profile)
        self.policy_enforcer.validate_metadata(profile, metadata or {})
        plan_result = self.planner.plan(goal, sandboxed_registry, preferences=preferences)
        context = ExecutionContext(profile=profile, metadata=metadata)
        return self.executor.execute_plan(plan_result.steps, sandboxed_registry, context, trace=plan_result.trace)
