import asyncio
import pathlib

import pytest

from cuga.mcp.config import MCPConfig
from cuga.mcp.interfaces import ToolRequest
from cuga.mcp.lifecycle import LifecycleManager
from cuga.mcp.registry import MCPRegistry


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

        async def bad_request(*args, **kwargs):
            raise RuntimeError("boom")

        runner = await manager.ensure_runner(cfg.tools["sample"])
        monkeypatch.setattr(runner, "call_with_retry", bad_request)
        for _ in range(3):
            with pytest.raises(RuntimeError):
                await runner.call_with_retry({}, timeout=0.1)
        with pytest.raises(Exception):
            await manager.call("sample", ToolRequest(method="echo"))
        await manager.stop_all()

    asyncio.run(_run())

