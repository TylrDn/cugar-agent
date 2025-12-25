"""Controller orchestrating planner and executor layers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict

from .audit import (
    AUDIT_EVENT_CONTROLLER_RUN,
    AUDIT_FIELD_EVENT,
    AUDIT_FIELD_GOAL,
    AUDIT_FIELD_POLICY,
    AUDIT_FIELD_PROFILE,
    AUDIT_POLICY_ALLOW,
    AUDIT_LOGGER_NAME,
    sanitize_for_audit,
)
from .executor import ExecutionContext, ExecutionResult, Executor
from .planner import Planner, PlanningPreferences
from .registry import ToolRegistry


@dataclass
class Controller:
    planner: Planner
    executor: Executor
    registry: ToolRegistry

    audit_logger = logging.getLogger(AUDIT_LOGGER_NAME)

    def run(
        self,
        goal: str,
        profile: str,
        *,
        metadata: Dict[str, Any] | None = None,
        preferences: PlanningPreferences | None = None,
    ) -> ExecutionResult:
        audit_entry = {
            AUDIT_FIELD_EVENT: AUDIT_EVENT_CONTROLLER_RUN,
            AUDIT_FIELD_PROFILE: sanitize_for_audit(profile),
            AUDIT_FIELD_GOAL: sanitize_for_audit(goal),
            AUDIT_FIELD_POLICY: AUDIT_POLICY_ALLOW,
        }
        audit_message = f"[audit] {audit_entry}"
        self.audit_logger.info(audit_message)

        sandboxed_registry = self.registry.sandbox(profile)
        plan_result = self.planner.plan(goal, sandboxed_registry, preferences=preferences)
        context = ExecutionContext(profile=profile, metadata=metadata)

        trace = [audit_message]
        trace.extend(plan_result.trace)

        return self.executor.execute_plan(plan_result.steps, sandboxed_registry, context, trace=trace)
