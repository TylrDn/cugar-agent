"""Task planner for controller-led orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List

from .registry import ToolRegistry


@dataclass
class PlanStep:
    """Single unit of work for the executor."""

    name: str
    tool: str
    input: dict[str, Any]


class Planner:
    """Builds a minimal plan from a goal and available tools."""

    def plan(self, goal: str, registry: ToolRegistry) -> List[PlanStep]:
        if not registry.profiles():
            raise ValueError("No profiles available for planning")
        profile = next(iter(registry.profiles()))
        profile_tools = registry.tools_for_profile(profile)
        if not profile_tools:
            raise ValueError(f"No tools registered for profile '{profile}'")
        tool_name = next(iter(profile_tools))
        return [PlanStep(name=f"fulfill:{goal}", tool=tool_name, input={"goal": goal, "profile": profile})]
