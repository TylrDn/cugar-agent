import asyncio
import asyncio
import pathlib

import pytest

from cuga.mcp.config import MCPConfig
from cuga.mcp.errors import CallTimeout, StartupError
from cuga.mcp.interfaces import ToolRequest
from cuga.mcp.lifecycle import LifecycleManager
from cuga.mcp.registry import MCPRegistry
from cuga.mcp.telemetry.metrics import metrics


def test_lifecycle_start_call_stop():
    cfg_path = pathlib.Path(__file__).with_name("sample_config.toml")
    cfg = MCPConfig.from_toml(str(cfg_path))

    async def _run():
        manager = LifecycleManager(MCPRegistry(cfg))
        response = await manager.call("sample", ToolRequest(method="echo", params={"value": "hi"}))
        assert response.ok
        assert response.result == {"value": "hi"}
        await manager.stop_all()

    asyncio.run(_run())


def test_circuit_breaker_opens_after_failures(monkeypatch):
    cfg_path = pathlib.Path(__file__).with_name("sample_config.toml")
    cfg = MCPConfig.from_toml(str(cfg_path))

    async def _run():
        manager = LifecycleManager(MCPRegistry(cfg))
        runner = await manager.ensure_runner(cfg.tools["sample"])

        async def bad_request(*args, **kwargs):
            raise CallTimeout("boom")

        monkeypatch.setattr(runner, "call_with_retry", bad_request)
        for _ in range(3):
            resp = await manager.call("sample", ToolRequest(method="echo"))
            assert not resp.ok
            assert "boom" in (resp.error or "")
        assert metrics.counter("mcp.calls").count >= 3
        resp = await manager.call("sample", ToolRequest(method="echo"))
        assert not resp.ok
        assert resp.error == "circuit open"
        await manager.stop_all()

    asyncio.run(_run())


def test_allow_commands_enforced():
    cfg_path = pathlib.Path(__file__).with_name("sample_config.toml")
    cfg = MCPConfig.from_toml(str(cfg_path))
    cfg.allow_commands = []

    async def _run():
        manager = LifecycleManager(MCPRegistry(cfg))
        resp = await manager.call("sample", ToolRequest(method="echo"))
        assert not resp.ok
        assert "not allowed" in (resp.error or "")
        with pytest.raises(StartupError):
            await manager.ensure_runner(cfg.tools["sample"])
        await manager.stop_all()

    asyncio.run(_run())

