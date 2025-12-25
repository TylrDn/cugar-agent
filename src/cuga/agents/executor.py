"""Plan executor that isolates each subagent call."""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List

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

    audit_logger = logging.getLogger("cuga.audit")

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
                "event": "tool_invocation",
                "profile": context.profile,
                "tool": step.tool,
                "input": step.input,
                "policy": "allow",
            }
            audit_message = f"[audit] {audit_entry}"
            self.audit_logger.info(audit_message)
            audit_trace.append(audit_message)

            try:
                result = handler(step.input, config=copy.deepcopy(config), context=context)
                success_entry = {**audit_entry, "outcome": "success"}
                success_message = f"[audit] {success_entry}"
                self.audit_logger.info(success_message)
                audit_trace.append(success_message)
            except Exception as exc:
                error_label = exc.__class__.__name__
                failure_entry = {**audit_entry, "outcome": "error", "error": error_label}
                failure_message = f"[audit] {failure_entry}"
                self.audit_logger.error(failure_message)
                audit_trace.append(failure_message)
                result = {
                    "status": "error",
                    "reason": "tool_execution_failed",
                    "detail": f"Tool '{step.tool}' failed with {error_label}",
                }

            step_results.append({"step": step.name, "tool": step.tool, "result": result})

        final_output = step_results[-1]["result"] if step_results else None
        return ExecutionResult(steps=step_results, output=final_output, trace=audit_trace)
