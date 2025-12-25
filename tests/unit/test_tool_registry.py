"""Unit tests for ToolRegistry isolation semantics."""

from __future__ import annotations

from typing import Any

from cuga.agents.registry import ToolRegistry


def _noop_handler(payload: dict[str, Any], *, config: dict[str, Any], context: Any) -> dict[str, Any]:
    return {"payload": payload, "config": config, "context": context}


class TestToolRegistryIsolation:
    def test_resolve_returns_isolated_copy(self) -> None:
        registry = ToolRegistry()
        registry.register("alpha", "echo", _noop_handler, config={"options": {"a": 1}})

        resolved_first = registry.resolve("alpha", "echo")
        resolved_first["config"]["options"]["a"] = 42

        resolved_second = registry.resolve("alpha", "echo")

        assert resolved_first is not resolved_second
        assert resolved_second["config"]["options"]["a"] == 1

    def test_tools_for_profile_returns_deep_copy(self) -> None:
        registry = ToolRegistry()
        registry.register("alpha", "echo", _noop_handler, config={"options": {"a": 1}})

        tools_snapshot = registry.tools_for_profile("alpha")
        tools_snapshot["echo"]["config"]["options"]["a"] = 99

        fresh_snapshot = registry.tools_for_profile("alpha")

        assert tools_snapshot is not fresh_snapshot
        assert fresh_snapshot["echo"]["config"]["options"]["a"] == 1
