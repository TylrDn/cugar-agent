from __future__ import annotations

import argparse
from cuga.modular.agents import PlannerAgent, WorkerAgent
from cuga.modular.memory import VectorMemory
from cuga.modular.tools import ToolRegistry, ToolSpec
from cuga.modular.observability import LangfuseEmitter


def main() -> None:
    parser = argparse.ArgumentParser(description="LangGraph-style planner/executor demo")
    parser.add_argument("--goal", required=True)
    parser.add_argument("--profile", default="demo_power")
    parser.add_argument("--observability", default="none", choices=["none", "langfuse"])
    args = parser.parse_args()

    registry = ToolRegistry(
        [ToolSpec(name="echo", description="Echo text", handler=lambda inputs, ctx: inputs.get("text", ""))]
    )
    memory = VectorMemory(profile=args.profile)
    planner = PlannerAgent(registry=registry, memory=memory)
    worker = WorkerAgent(registry=registry, memory=memory, observability=_maybe_emitter(args.observability))

    plan = planner.plan(goal=args.goal, metadata={"profile": args.profile})
    result = worker.execute(plan.steps, metadata={"profile": args.profile})
    print("Plan:", plan.steps)
    print("Result:", result.output)


def _maybe_emitter(name: str):
    if name == "langfuse":
        return LangfuseEmitter()
    return None


if __name__ == "__main__":
    main()
