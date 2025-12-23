from __future__ import annotations

# REVIEW-FIX: Safe sync wrapper parity; resilient thread/loop lifecycle.

import atexit
import asyncio
import threading
from concurrent.futures import Future
from typing import Any, Coroutine

from langchain.tools import BaseTool

from cuga.mcp.adapters.mcp_tool import MCPToolHandle
from cuga.mcp.interfaces import ToolRequest


class AsyncWorker:
    """Singleton async worker running a shared event loop."""

    _instance_lock = threading.Lock()
    _instance: AsyncWorker | None = None

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_ready = threading.Event()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._loop_ready.wait()

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        loop = self._loop
        if loop is None or loop.is_closed():
            raise RuntimeError("AsyncWorker loop is not running")
        return loop

    @classmethod
    def instance(cls) -> AsyncWorker:
        if cls._instance and cls._instance._is_running:
            return cls._instance
        with cls._instance_lock:
            if cls._instance and cls._instance._is_running:
                return cls._instance
            cls._instance = cls()
        return cls._instance

    def submit(self, coro: Coroutine[Any, Any, Any]) -> Future[Any]:
        """Submit coroutine to the shared loop."""

        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    def stop(self) -> None:
        loop = self._loop
        if not loop or loop.is_closed():
            return
        loop.call_soon_threadsafe(loop.stop)
        self._thread.join()

    @property
    def _is_running(self) -> bool:
        return self._loop_ready.is_set() and self._loop is not None and not self._loop.is_closed()

    def _run_loop(self) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        self._loop_ready.set()
        try:
            loop.run_forever()
        finally:
            tasks = asyncio.all_tasks(loop)
            if tasks:
                for task in tasks:
                    task.cancel()
                loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()


atexit.register(lambda: AsyncWorker._instance and AsyncWorker._instance.stop())


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

        worker = AsyncWorker.instance()
        result = worker.submit(coro)
        try:
            return result.result()
        except KeyboardInterrupt:
            result.cancel()
            raise

    async def _arun(self, tool_input: str, run_manager=None):  # type: ignore[override]
        req = ToolRequest(method="invoke", params={"input": tool_input})
        resp = await self.handle.call(req)
        if resp.ok:
            return resp.result
        raise RuntimeError(resp.error or "unknown MCP error")
