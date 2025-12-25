from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, List, Optional

from .config import AgentConfig
from .memory import VectorMemory
from .tools import ToolRegistry, ToolSpec
from .observability import BaseEmitter


@dataclass
class AgentPlan:
    steps: List[dict]
    trace: List[dict] = field(default_factory=list)


@dataclass
class AgentResult:
    output: Any
    trace: List[dict] = field(default_factory=list)


@dataclass
class PlannerAgent:
    registry: ToolRegistry
    memory: VectorMemory
    config: AgentConfig = field(default_factory=AgentConfig.from_env)

    def plan(self, goal: str, metadata: Optional[dict] = None) -> AgentPlan:
        metadata = metadata or {}
        trace = [
            {
                "event": "plan:start",
                "goal": goal,
                "profile": metadata.get("profile", self.config.profile),
            }
        ]
        steps = [{"tool": tool.name, "input": {"text": goal}} for tool in self.registry.tools]
        trace.append({"event": "plan:steps", "count": len(steps)})
        self.memory.remember(goal, metadata={"profile": metadata.get("profile", self.config.profile)})
        return AgentPlan(steps=steps, trace=trace)


@dataclass
class WorkerAgent:
    registry: ToolRegistry
    memory: VectorMemory
    observability: Optional[BaseEmitter] = None

    def execute(self, steps: Iterable[dict], metadata: Optional[dict] = None) -> AgentResult:
        metadata = metadata or {}
        profile = metadata.get("profile", "default")
        trace: List[dict] = []
        output: Any = None
        for idx, step in enumerate(steps):
            tool = self.registry.get(step["tool"])
            if tool is None:
                raise ValueError(f"Tool {step['tool']} not registered")
            result = tool.handler(step.get("input", {}), {"profile": profile})
            output = result
            trace.append({"event": "execute:step", "tool": tool.name, "index": idx})
            if self.observability:
                self.observability.emit({"event": "tool", "name": tool.name, "profile": profile})
        self.memory.remember(str(output), metadata={"profile": profile})
        return AgentResult(output=output, trace=trace)


@dataclass
class CoordinatorAgent:
    planner: PlannerAgent
    workers: List[WorkerAgent]
    memory: VectorMemory

    def dispatch(self, goal: str) -> AgentResult:
        plan = self.planner.plan(goal, metadata={"profile": self.planner.config.profile})
        traces = list(plan.trace)
        if not self.workers:
            raise ValueError("No workers configured")
        worker = self.workers[0]
        result = worker.execute(plan.steps, metadata={"profile": self.planner.config.profile})
        traces.extend(result.trace)
        return AgentResult(output=result.output, trace=traces)


def build_default_registry() -> ToolRegistry:
    return ToolRegistry(
        [
            ToolSpec(name="echo", description="Echo text", handler=lambda inputs, ctx: inputs.get("text", "")),
        ]
    )
