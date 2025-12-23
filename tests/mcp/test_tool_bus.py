import asyncio
import pathlib

from cuga.mcp.adapters.mcp_tool import MCPToolHandle
from cuga.mcp.config import MCPConfig
from cuga.mcp.interfaces import ToolRequest
from cuga.mcp.lifecycle import LifecycleManager
from cuga.mcp.registry import MCPRegistry
from cuga.mcp.tool_bus import ToolBus


def test_tool_bus_call():
    cfg_path = pathlib.Path(__file__).with_name("sample_config.toml")
    cfg = MCPConfig.from_toml(str(cfg_path))

    async def _run():
        bus = ToolBus(LifecycleManager(MCPRegistry(cfg)))
        resp = await bus.call("sample", "echo", {"value": "bus"})
        assert resp.ok
        assert resp.result == {"value": "bus"}
        assert "sample" in bus.list_tools()
        await bus.lifecycle.stop_all()

    asyncio.run(_run())


def test_tool_bus_failure_propagates():
    cfg_path = pathlib.Path(__file__).with_name("sample_config.toml")
    cfg = MCPConfig.from_toml(str(cfg_path))
    cfg.allow_commands = []

    async def _run():
        bus = ToolBus(LifecycleManager(MCPRegistry(cfg)))
        resp = await bus.call("sample", "echo", {})
        assert not resp.ok
        assert resp.error
        await bus.lifecycle.stop_all()

    asyncio.run(_run())

