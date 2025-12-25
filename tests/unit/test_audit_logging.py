"""Audit logging and failure handling for controller and executor."""

from __future__ import annotations

import logging

from cuga.agents.controller import Controller
from cuga.agents.executor import Executor
from cuga.agents.planner import Planner
from cuga.agents.registry import ToolRegistry


def _success_tool(payload: dict[str, str], *, config: dict, context: object) -> dict:
    return {"echo": payload, "config": config, "profile": getattr(context, "profile", None)}


def _failing_tool(_payload: dict[str, str], *, config: dict, context: object) -> None:
    raise RuntimeError("secret failure")


def test_audit_trace_and_logs_for_success(caplog: object) -> None:
    registry = ToolRegistry()
    registry.register("alpha", "ok", _success_tool, config={"safe": True})
    controller = Controller(planner=Planner(), executor=Executor(), registry=registry)

    caplog.set_level(logging.INFO, logger="cuga.audit")

    result = controller.run(goal="demo", profile="alpha")

    assert any("controller.run" in message for message in result.trace)
    assert any("tool_invocation" in message and "ok" in message for message in result.trace)
    assert any("outcome" in message and "success" in message for message in result.trace)
    assert any("controller.run" in record.message for record in caplog.records)
    assert any("tool_invocation" in record.message for record in caplog.records)

    assert result.output["echo"] == {"goal": "demo", "profile": "alpha", "sequence": 1}


def test_audit_trace_and_sanitized_failure(caplog: object) -> None:
    registry = ToolRegistry()
    registry.register("alpha", "boom", _failing_tool)
    controller = Controller(planner=Planner(), executor=Executor(), registry=registry)

    caplog.set_level(logging.INFO, logger="cuga.audit")

    result = controller.run(goal="demo", profile="alpha")

    assert any("outcome" in message and "error" in message for message in result.trace)
    assert any("RuntimeError" in message for message in result.trace)
    assert any("boom" in record.message for record in caplog.records)
    assert result.output["status"] == "error"
    assert result.output["reason"] == "tool_execution_failed"
    assert result.output["detail"] == "Tool 'boom' failed with RuntimeError"
    assert "secret failure" not in str(result.output)
    assert "secret failure" not in "".join(result.trace)


def test_audit_trace_preserves_planner_trace_order() -> None:
    class StubPlanner(Planner):
        def plan(self, goal: str, registry: ToolRegistry, preferences=None):  # type: ignore[override]
            plan_result = super().plan(goal, registry, preferences=preferences)
            plan_result.trace = ["planner-step-1"]
            return plan_result

    registry = ToolRegistry()
    registry.register("alpha", "ok", _success_tool, config={"safe": True})
    controller = Controller(planner=StubPlanner(), executor=Executor(), registry=registry)

    result = controller.run(goal="demo", profile="alpha")

    assert result.trace[0].startswith("[audit]") and "controller.run" in result.trace[0]
    assert result.trace[1:] == ["planner-step-1"] + result.trace[2:]
    assert any("tool_invocation" in message for message in result.trace[1:])
