from __future__ import annotations

# REVIEW-FIX: Safe sync wrapper parity; resilient thread/loop lifecycle.

import asyncio
import threading
from concurrent.futures import Future
from typing import Any

from langchain.tools import BaseTool

from cuga.mcp.adapters.mcp_tool import MCPToolHandle
from cuga.mcp.interfaces import ToolRequest


class LangChainMCPTool(BaseTool):
    name: str
    description: str = "MCP tool"

    def __init__(self, handle: MCPToolHandle, description: str = "MCP tool"):
        super().__init__()
        self.handle = handle
        self.name = handle.alias
        self.description = description

    def _run(self, tool_input: str, run_manager=None):  # type: ignore[override]
        coro = self._arun(tool_input, run_manager)
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)

        result: Future[Any] = Future()
        loop_ready = threading.Event()
        loop_holder: dict[str, asyncio.AbstractEventLoop] = {}
        task_holder: dict[str, asyncio.Task[Any]] = {}

        def runner() -> None:
            loop = asyncio.new_event_loop()
            loop_holder["loop"] = loop
            asyncio.set_event_loop(loop)
            loop_ready.set()
            try:
                task = loop.create_task(coro)
                task_holder["task"] = task
                res = loop.run_until_complete(task)
            except BaseException as exc:  # noqa: BLE001 - propagate original
                result.set_exception(exc)
            else:
                result.set_result(res)
            finally:
                loop.run_until_complete(loop.shutdown_asyncgens())
                loop.close()

        thread = threading.Thread(target=runner, daemon=True)
        thread.start()
        loop_ready.wait()
        try:
            return result.result()
        except KeyboardInterrupt:
            loop = loop_holder.get("loop")
            task = task_holder.get("task")
            if loop and task and not loop.is_closed():
                loop.call_soon_threadsafe(task.cancel)
            raise
        finally:
            thread.join()

    async def _arun(self, tool_input: str, run_manager=None):  # type: ignore[override]
        req = ToolRequest(method="invoke", params={"input": tool_input})
        resp = await self.handle.call(req)
        if resp.ok:
            return resp.result
        raise RuntimeError(resp.error or "unknown MCP error")
