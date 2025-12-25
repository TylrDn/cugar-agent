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
    assert any("outcome': 'success'" in message for message in result.trace)
    assert any("controller.run" in record.message for record in caplog.records)
    assert any("tool_invocation" in record.message for record in caplog.records)

    assert result.output["echo"] == {"goal": "demo", "profile": "alpha", "sequence": 1}


def test_audit_trace_and_sanitized_failure(caplog: object) -> None:
    registry = ToolRegistry()
    registry.register("alpha", "boom", _failing_tool)
    controller = Controller(planner=Planner(), executor=Executor(), registry=registry)

    caplog.set_level(logging.INFO, logger="cuga.audit")

    result = controller.run(goal="demo", profile="alpha")

    assert any("outcome': 'error'" in message for message in result.trace)
    assert any("RuntimeError" in message for message in result.trace)
    assert any("boom" in record.message for record in caplog.records)
    assert result.output["reason"] == "tool_execution_failed"
    assert "secret failure" not in str(result.output)
    assert "secret failure" not in "".join(result.trace)
