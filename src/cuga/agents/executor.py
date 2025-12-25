"""Plan executor that isolates each subagent call."""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List

from .audit import (
    AUDIT_ERROR_REASON,
    AUDIT_EVENT_TOOL_INVOCATION,
    AUDIT_FIELD_ERROR,
    AUDIT_FIELD_EVENT,
    AUDIT_FIELD_INPUT,
    AUDIT_FIELD_OUTCOME,
    AUDIT_FIELD_POLICY,
    AUDIT_FIELD_PROFILE,
    AUDIT_FIELD_TOOL,
    AUDIT_LOGGER_NAME,
    AUDIT_OUTCOME_ERROR,
    AUDIT_OUTCOME_SUCCESS,
    AUDIT_POLICY_ALLOW,
    sanitize_for_audit,
)
from .planner import PlanStep
from .registry import ToolRegistry


@dataclass
class ExecutionContext:
    profile: str
    metadata: Dict[str, Any] | None = None


@dataclass
class ExecutionResult:
    steps: List[Dict[str, Any]]
    output: Any | None = None
    trace: List[str] | None = None


class Executor:
    """Executes a plan using tools from an isolated registry view."""

    audit_logger = logging.getLogger(AUDIT_LOGGER_NAME)

    def execute_plan(
        self, plan: Iterable[PlanStep], registry: ToolRegistry, context: ExecutionContext, trace: List[str] | None = None
    ) -> ExecutionResult:
        step_results: List[Dict[str, Any]] = []
        audit_trace: List[str] = list(trace or [])

        for step in plan:
            tool_entry = registry.resolve(context.profile, step.tool)
            handler = tool_entry["handler"]
            config = tool_entry.get("config", {})

            audit_entry = {
                AUDIT_FIELD_EVENT: AUDIT_EVENT_TOOL_INVOCATION,
                AUDIT_FIELD_PROFILE: sanitize_for_audit(context.profile),
                AUDIT_FIELD_TOOL: step.tool,
                AUDIT_FIELD_INPUT: sanitize_for_audit(step.input),
                AUDIT_FIELD_POLICY: AUDIT_POLICY_ALLOW,
            }
            audit_message = f"[audit] {audit_entry}"
            self.audit_logger.info(audit_message)
            audit_trace.append(audit_message)

            try:
                result = handler(step.input, config=copy.deepcopy(config), context=context)
                success_entry = {**audit_entry, AUDIT_FIELD_OUTCOME: AUDIT_OUTCOME_SUCCESS}
                success_message = f"[audit] {success_entry}"
                self.audit_logger.info(success_message)
                audit_trace.append(success_message)
            except Exception as exc:
                error_label = exc.__class__.__name__
                failure_entry = {
                    **audit_entry,
                    AUDIT_FIELD_OUTCOME: AUDIT_OUTCOME_ERROR,
                    AUDIT_FIELD_ERROR: error_label,
                }
                failure_message = f"[audit] {failure_entry}"
                self.audit_logger.exception(failure_message)
                audit_trace.append(failure_message)
                result = {
                    "status": "error",
                    "reason": AUDIT_ERROR_REASON,
                    "detail": f"Tool '{step.tool}' failed with {error_label}",
                }

            step_results.append({"step": step.name, "tool": step.tool, "result": result})

        final_output = step_results[-1]["result"] if step_results else None
        return ExecutionResult(steps=step_results, output=final_output, trace=audit_trace)
