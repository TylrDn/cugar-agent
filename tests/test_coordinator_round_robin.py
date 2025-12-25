from __future__ import annotations

import threading

from cuga.modular.agents import CoordinatorAgent, PlannerAgent, WorkerAgent
from cuga.modular.memory import VectorMemory
from cuga.modular.tools import ToolRegistry, ToolSpec


def test_coordinator_round_robin_thread_safe() -> None:
    registry = ToolRegistry([ToolSpec(name="echo", description="", handler=lambda i, c: i.get("text", ""))])
    memory = VectorMemory()
    planner = PlannerAgent(registry=registry, memory=memory)
    workers = [WorkerAgent(registry=registry, memory=memory) for _ in range(2)]
    coordinator = CoordinatorAgent(planner=planner, workers=workers, memory=memory)

    outputs: list[str] = []

    def run(goal: str) -> None:
        result = coordinator.dispatch(goal)
        outputs.append(result.output)

    threads = [threading.Thread(target=run, args=(f"goal {i}",)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(outputs) == 4
    # With two workers round-robin, first two outputs should come from alternating workers (order preserved via lock)
    assert coordinator._next_worker_idx == 0
