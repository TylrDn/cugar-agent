from __future__ import annotations

from typing import Any, Awaitable, Callable

from cuga.mcp.adapters.mcp_tool import MCPToolHandle
from cuga.mcp.interfaces import ToolRequest

def autogen_callable(handle: MCPToolHandle) -> Callable[[str], Awaitable[Any]]:
    async def _call(prompt: str) -> Any:
        resp = await handle.call(ToolRequest(method="invoke", params={"input": prompt}))
        if resp.ok:
            return resp.result
        raise RuntimeError(resp.error or "unknown MCP error")

    return _call
