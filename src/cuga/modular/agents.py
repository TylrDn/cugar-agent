from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Iterable, List, Optional

from .config import AgentConfig
from .llm.interface import LLM, MockLLM
from .memory import VectorMemory
from .observability import BaseEmitter
from .tools import ToolRegistry, ToolSpec


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
    llm: LLM = field(default_factory=MockLLM)

    def plan(self, goal: str, metadata: Optional[dict] = None) -> AgentPlan:
        metadata = metadata or {}
        profile = metadata.get("profile", self.config.profile)
        trace_id = metadata.get("trace_id")
        trace = [
            {"event": "plan:start", "goal": goal, "profile": profile, "trace_id": trace_id},
        ]
        scored_tools = self._rank_tools(goal)
        selected = scored_tools[: max(1, min(self.config.max_steps, len(scored_tools)))]
        steps: List[dict] = []
        for idx, (tool, score) in enumerate(selected):
            steps.append(
                {
                    "tool": tool.name,
                    "input": {"text": goal},
                    "reason": f"matched with score {score:.2f}",
                    "trace_id": trace_id,
                    "index": idx,
                }
            )
        trace.append({"event": "plan:steps", "count": len(steps), "trace_id": trace_id})
        self.memory.remember(goal, metadata={"profile": profile, "trace_id": trace_id})
        trace.append({"event": "plan:complete", "profile": profile, "trace_id": trace_id})
        return AgentPlan(steps=steps, trace=trace)

    def _rank_tools(self, goal: str) -> List[tuple[ToolSpec, float]]:
        import re

        terms = set(re.split(r"\W+", goal.lower()))
        ranked: List[tuple[ToolSpec, float]] = []
        for tool in self.registry.tools:
            corpus_text = f"{tool.name} {tool.description}".lower()
            corpus = set(re.split(r"\W+", corpus_text))
            overlap = len(terms.intersection(corpus))
            score = overlap / max(len(terms), 1)
            if score > 0:
                ranked.append((tool, score))
        ranked.sort(key=lambda item: item[1], reverse=True)
        return ranked


@dataclass
class WorkerAgent:
    registry: ToolRegistry
    memory: VectorMemory
    observability: Optional[BaseEmitter] = None

    def execute(self, steps: Iterable[dict], metadata: Optional[dict] = None) -> AgentResult:
        metadata = metadata or {}
        profile = metadata.get("profile", self.memory.profile)
        trace_id = metadata.get("trace_id")
        trace: List[dict] = []
        output: Any = None
        for idx, step in enumerate(steps):
            tool = self.registry.get(step["tool"])
            if tool is None:
                raise ValueError(f"Tool {step['tool']} not registered")
            context = {"profile": profile, "trace_id": trace_id}
            result = tool.handler(step.get("input", {}), context)
            output = result
            event = {"event": "execute:step", "tool": tool.name, "index": idx, "trace_id": trace_id}
            trace.append(event)
            if self.observability:
                self.observability.emit({"event": "tool", "name": tool.name, "profile": profile, "trace_id": trace_id})
        self.memory.remember(str(output), metadata={"profile": profile, "trace_id": trace_id})
        return AgentResult(output=output, trace=trace)


@dataclass
class CoordinatorAgent:
    planner: PlannerAgent
    workers: List[WorkerAgent]
    memory: VectorMemory
    _next_worker_idx: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def dispatch(self, goal: str, trace_id: Optional[str] = None) -> AgentResult:
        plan = self.planner.plan(goal, metadata={"profile": self.planner.config.profile, "trace_id": trace_id})
        traces = list(plan.trace)
        if not self.workers:
            raise ValueError("No workers configured")
        worker = self._select_worker()
        result = worker.execute(plan.steps, metadata={"profile": self.planner.config.profile, "trace_id": trace_id})
        traces.extend(result.trace)
        return AgentResult(output=result.output, trace=traces)

    def _select_worker(self) -> WorkerAgent:
        with self._lock:
            if not self.workers:
                raise ValueError("No workers available to select from.")
            worker = self.workers[self._next_worker_idx]
            self._next_worker_idx = (self._next_worker_idx + 1) % len(self.workers)
        return worker


def build_default_registry() -> ToolRegistry:
    return ToolRegistry(
        [
            ToolSpec(name="echo", description="Echo text", handler=lambda inputs, ctx: inputs.get("text", "")),
        ]
    )
