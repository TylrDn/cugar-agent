"""Plan executor that isolates each subagent call."""

from __future__ import annotations

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


class Executor:
    """Executes a plan using tools from an isolated registry view."""

    def execute_plan(self, plan: Iterable[PlanStep], registry: ToolRegistry, context: ExecutionContext) -> ExecutionResult:
        step_results: List[Dict[str, Any]] = []
        for step in plan:
            tool_entry = registry.resolve(context.profile, step.tool)
            handler = tool_entry["handler"]
            config = tool_entry.get("config", {})
            result = handler(step.input, config=config, context=context)
            step_results.append({"step": step.name, "tool": step.tool, "result": result})
        final_output = step_results[-1]["result"] if step_results else None
        return ExecutionResult(steps=step_results, output=final_output)
