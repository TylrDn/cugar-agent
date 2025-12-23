import asyncio
import sys
import threading
import types


def _install_langchain_stub() -> None:
    langchain = types.ModuleType("langchain")
    tools = types.ModuleType("langchain.tools")

    class BaseTool:  # pragma: no cover - shim
        name: str
        description: str

    tools.BaseTool = BaseTool  # type: ignore[attr-defined]
    langchain.tools = tools  # type: ignore[attr-defined]
    sys.modules.setdefault("langchain", langchain)
    sys.modules.setdefault("langchain.tools", tools)


_install_langchain_stub()

from cuga.mcp.adapters.langchain_adapter import LangChainMCPTool
from cuga.mcp.interfaces import ToolResponse


class FakeHandle:
    def __init__(self, result):
        self.alias = "fake"
        self._result = result

    async def call(self, req):
        return ToolResponse(ok=True, result=req.params["input"]) if self._result == "ok" else ToolResponse(ok=False, error="err")


def test_run_without_loop():
    tool = LangChainMCPTool(FakeHandle("ok"))
    before = threading.active_count()
    assert tool._run("hi") == "hi"
    assert threading.active_count() <= before + 1


def test_run_with_running_loop_same_thread():
    tool = LangChainMCPTool(FakeHandle("ok"))

    async def main():
        return tool._run("loop")

    assert asyncio.run(main()) == "loop"


def test_run_with_loop_other_thread():
    tool = LangChainMCPTool(FakeHandle("ok"))
    result_holder = {}

    def worker():
        async def main():
            result_holder["value"] = tool._run("thread")
        asyncio.run(main())

    before = threading.active_count()
    t = threading.Thread(target=worker)
    t.start()
    t.join()
    assert result_holder["value"] == "thread"
    assert threading.active_count() <= before + 2
