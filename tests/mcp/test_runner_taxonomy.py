import asyncio

import pytest

from cuga.mcp.errors import CallTimeout, StartupError
from cuga.mcp.runners.subprocess_stdio import SubprocessStdioRunner


def test_runner_timeout_and_eof(monkeypatch):
    async def _run():
        runner = SubprocessStdioRunner("python", args=["-m", "tests.mcp.echo_server"])
        await runner.start()

        async def slow_read():
            await asyncio.sleep(0.05)
            return b""

        monkeypatch.setattr(runner.process.stdout, "readline", slow_read)  # type: ignore[arg-type]
        with pytest.raises(CallTimeout):
            await runner.request({"method": "echo", "params": {}}, timeout=0.01)
        runner.process.kill()
        await runner.process.wait()
        with pytest.raises(StartupError):
            await runner.request({"method": "echo", "params": {}}, timeout=0.1)
        await runner.stop()

    asyncio.run(_run())


def test_runner_restarts_after_startup_error():
    async def _run():
        runner = SubprocessStdioRunner("python", args=["-m", "tests.mcp.echo_server"])
        await runner.start()
        runner.process.kill()
        await runner.process.wait()
        result = await runner.call_with_retry({"method": "health", "params": {}}, timeout=0.5, attempts=2)
        assert result["result"] == "ok"
        await runner.stop()

    asyncio.run(_run())
