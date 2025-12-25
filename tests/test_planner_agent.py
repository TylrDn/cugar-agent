from __future__ import annotations

from cuga.modular.agents import PlannerAgent
from cuga.modular.memory import VectorMemory
from cuga.modular.tools import ToolRegistry, ToolSpec


def test_planner_selects_relevant_tools_only() -> None:
    registry = ToolRegistry(
        [
            ToolSpec(name="echo", description="echo text", handler=lambda i, c: i.get("text")),
            ToolSpec(name="calc", description="math operations", handler=lambda i, c: "0"),
        ]
    )
    planner = PlannerAgent(registry=registry, memory=VectorMemory())
    plan = planner.plan("echo greeting")
    assert len(plan.steps) == 1
    assert plan.steps[0]["tool"] == "echo"
