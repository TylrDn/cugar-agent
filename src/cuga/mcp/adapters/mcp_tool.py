from __future__ import annotations

from cuga.mcp.interfaces import MCPTool, ToolRequest, ToolResponse
from cuga.mcp.lifecycle import LifecycleManager


class MCPToolHandle(MCPTool):
    def __init__(self, lifecycle: LifecycleManager, alias: str):
        self.lifecycle = lifecycle
        self.alias = alias

    async def start(self) -> None:
        await self.lifecycle.ensure_runner(self.lifecycle.registry.get(self.alias))

    async def stop(self) -> None:
        await self.lifecycle.stop_runner(self.alias)

    async def call(self, req: ToolRequest) -> ToolResponse:
        return await self.lifecycle.call(self.alias, req)
