import pytest

from cuga.agents.executor import ExecutionContext, Executor
from cuga.agents.planner import Planner, PlanStep
from cuga.agents.registry import ToolRegistry


def test_planner_deterministic_sorting():
    registry = ToolRegistry()
    registry.register("beta", "zeta", lambda *_args, **_kwargs: None)
    registry.register("alpha", "omega", lambda *_args, **_kwargs: None)
    registry.register("alpha", "alpha_tool", lambda *_args, **_kwargs: None)

    planner = Planner()
    plan = planner.plan("goal", registry)

    assert plan[0].tool == "alpha_tool"
    assert plan[0].input["profile"] == "alpha"


def test_toolregistry_sandbox_isolated_mutation():
    registry = ToolRegistry()
    registry.register(
        "profile",
        "tool",
        lambda *_args, **_kwargs: None,
        config={"value": 1},
    )

    sandboxed = registry.sandbox("profile")

    # Mutating the sandboxed registry's config does not affect the original.
    sandbox_tool = sandboxed.resolve("profile", "tool")
    sandbox_tool["config"]["value"] = 2
    assert registry.resolve("profile", "tool")["config"]["value"] == 1

    # Mutating the original registry's config does not affect the sandbox.
    original_tool = registry.resolve("profile", "tool")
    original_tool["config"]["value"] = 3
    assert sandboxed.resolve("profile", "tool")["config"]["value"] == 2


def test_toolregistry_sandbox_missing_profile_raises():
    registry = ToolRegistry()

    with pytest.raises(KeyError):
        registry.sandbox("missing")


def test_toolregistry_merge_deep_independence_and_conflict_detection():
    registry_a = ToolRegistry()
    registry_b = ToolRegistry()

    registry_a.register(
        "profile",
        "tool_a",
        lambda *_args, **_kwargs: None,
        config={"value": 1},
    )
    registry_b.register(
        "profile",
        "tool_b",
        lambda *_args, **_kwargs: None,
        config={"value": 2},
    )

    merged = registry_a.merge(registry_b)

    merged_tool_a = merged.resolve("profile", "tool_a")
    merged_tool_b = merged.resolve("profile", "tool_b")

    merged_tool_a["config"]["value"] = 10
    merged_tool_b["config"]["value"] = 20

    assert registry_a.resolve("profile", "tool_a")["config"]["value"] == 1
    assert registry_b.resolve("profile", "tool_b")["config"]["value"] == 2

    registry_a.resolve("profile", "tool_a")["config"]["value"] = 100
    registry_b.resolve("profile", "tool_b")["config"]["value"] = 200

    assert merged.resolve("profile", "tool_a")["config"]["value"] == 10
    assert merged.resolve("profile", "tool_b")["config"]["value"] == 20

    conflict_a = ToolRegistry()
    conflict_b = ToolRegistry()

    conflict_a.register(
        "profile",
        "conflict_tool",
        lambda *_args, **_kwargs: None,
        config={"value": "a"},
    )
    conflict_b.register(
        "profile",
        "conflict_tool",
        lambda *_args, **_kwargs: None,
        config={"value": "b"},
    )

    with pytest.raises(ValueError):
        conflict_a.merge(conflict_b)


def test_executor_handler_receives_config_copy():
    registry = ToolRegistry()

    base_config = {"counter": 0}
    seen_counters = []

    def handler(*_args, **kwargs):
        cfg = kwargs["config"]
        cfg["counter"] += 1
        seen_counters.append(cfg["counter"])
        return "ok"

    registry.register(
        "counter_tool",
        "default",
        handler,
        config=base_config,
    )

    sandbox = registry.sandbox("counter_tool")
    executor = Executor()
    plan = [PlanStep(name="counter", tool="default", input={})]
    context = ExecutionContext(profile="counter_tool")

    executor.execute_plan(plan, sandbox, context)
    executor.execute_plan(plan, sandbox, context)

    assert seen_counters == [1, 1]

    stored_tool = registry.resolve("counter_tool", "default")
    assert stored_tool["config"] is not base_config
    assert stored_tool["config"]["counter"] == 0
    assert base_config["counter"] == 0
