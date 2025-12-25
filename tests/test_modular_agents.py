from cuga.modular.agents import PlannerAgent, WorkerAgent, CoordinatorAgent
from cuga.modular.tools import ToolRegistry, ToolSpec
from cuga.modular.memory import VectorMemory


def test_planner_and_worker_flow():
    registry = ToolRegistry([ToolSpec(name="echo", description="echo", handler=lambda inp, ctx: inp["text"])])
    memory = VectorMemory(profile="test")
    planner = PlannerAgent(registry=registry, memory=memory)
    worker = WorkerAgent(registry=registry, memory=memory)

    plan = planner.plan(goal="hello", metadata={"profile": "test"})
    result = worker.execute(plan.steps, metadata={"profile": "test"})

    assert result.output == "hello"
    assert memory.search("hello")


def test_coordinator_dispatches_first_worker():
    registry = ToolRegistry([ToolSpec(name="echo", description="echo", handler=lambda inp, ctx: inp["text"])])
    memory = VectorMemory(profile="test")
    planner = PlannerAgent(registry=registry, memory=memory)
    worker = WorkerAgent(registry=registry, memory=memory)
    coordinator = CoordinatorAgent(planner=planner, workers=[worker], memory=memory)

    result = coordinator.dispatch(goal="run")
    assert result.output == "run"
