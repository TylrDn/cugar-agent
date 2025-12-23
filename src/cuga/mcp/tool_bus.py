from __future__ import annotations

# REVIEW-FIX: Propagate lifecycle errors consistently through ToolBus.

from cuga.mcp.adapters.mcp_tool import MCPToolHandle
from cuga.mcp.interfaces import ToolRequest, ToolResponse
from cuga.mcp.lifecycle import LifecycleManager


class ToolBus:
    def __init__(self, lifecycle: LifecycleManager | None = None) -> None:
        self.lifecycle = lifecycle or LifecycleManager()

    async def call(self, alias: str, method: str, params: dict | None = None, timeout_s: float | None = None) -> ToolResponse:
        handle = MCPToolHandle(self.lifecycle, alias)
        return await handle.call(ToolRequest(method=method, params=params or {}, timeout_s=timeout_s))

    def list_tools(self) -> list[str]:
        return [spec.alias for spec in self.lifecycle.registry.list()]
