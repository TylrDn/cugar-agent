from __future__ import annotations

from typing import Optional

from langchain.tools import BaseTool

from cuga.mcp.interfaces import ToolRequest
from cuga.mcp.adapters.mcp_tool import MCPToolHandle


class LangChainMCPTool(BaseTool):
    name: str
    description: str = "MCP tool"

    def __init__(self, handle: MCPToolHandle, description: str = "MCP tool"):
        super().__init__()
        self.handle = handle
        self.name = handle.alias
        self.description = description

    def _run(self, tool_input: str, run_manager=None):  # type: ignore[override]
        request = ToolRequest(method="invoke", params={"input": tool_input})
        return self.handle.lifecycle.registry.get(self.handle.alias).transport + ":" + tool_input

    async def _arun(self, tool_input: str, run_manager=None):  # type: ignore[override]
        req = ToolRequest(method="invoke", params={"input": tool_input})
        resp = await self.handle.call(req)
        if resp.ok:
            return resp.result
        raise RuntimeError(resp.error or "unknown MCP error")
