from __future__ import annotations

import argparse
from cuga.modular.agents import CoordinatorAgent, PlannerAgent, WorkerAgent
from cuga.modular.memory import VectorMemory
from cuga.modular.tools import ToolRegistry, ToolSpec


def main() -> None:
    parser = argparse.ArgumentParser(description="CrewAI/AutoGen style dispatcher")
    parser.add_argument("--goal", required=True)
    args = parser.parse_args()

    registry = ToolRegistry(
        [ToolSpec(name="echo", description="Echo text", handler=lambda inputs, ctx: inputs.get("text", ""))]
    )
    memory = VectorMemory(profile="multi")
    planner = PlannerAgent(registry=registry, memory=memory)
    workers = [WorkerAgent(registry=registry, memory=memory) for _ in range(2)]
    coordinator = CoordinatorAgent(planner=planner, workers=workers, memory=memory)

    outcome = coordinator.dispatch(goal=args.goal)
    print(outcome.output)


if __name__ == "__main__":
    main()
