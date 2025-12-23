import asyncio
import os
import sys

import pytest

from cuga.mcp.errors import CallTimeout, StartupError
from cuga.mcp.runners.subprocess_stdio import SubprocessStdioRunner


def test_runner_timeout_and_eof(monkeypatch):
    async def _run():
        runner = SubprocessStdioRunner(sys.executable, args=["-m", "tests.mcp.echo_server"])
        await runner.start()

        async def slow_read():
            await asyncio.sleep(0.05)
            return ""

        monkeypatch.setattr(runner.process.stdout, "readline", slow_read)  # type: ignore[arg-type]
        with pytest.raises(CallTimeout):
            await runner.request({"method": "echo", "params": {}}, timeout=0.01)
        runner.process.kill()
        await runner.process.wait()
        with pytest.raises(StartupError):
            await runner.request({"method": "echo", "params": {}}, timeout=0.1)
        await runner.stop()

    asyncio.run(_run())


def test_startup_invalid_json_and_eof():
    async def _run_invalid():
        runner = SubprocessStdioRunner(
            sys.executable,
            args=["-c", "import sys; sys.stdout.write('invalid\\n'); sys.stdout.flush(); sys.exit(0)"]
        )
        with pytest.raises(StartupError):
            await runner.start()

    asyncio.run(_run_invalid())

    async def _run_eof():
        runner = SubprocessStdioRunner(sys.executable, args=["-c", "import sys; sys.exit(0)"])
        with pytest.raises(StartupError):
            await runner.start()

    asyncio.run(_run_eof())


def test_runner_restarts_after_startup_error():
    async def _run():
        runner = SubprocessStdioRunner(sys.executable, args=["-m", "tests.mcp.echo_server"])
        await runner.start()
        runner.process.kill()
        await runner.process.wait()
        result = await runner.call_with_retry({"method": "health", "params": {}}, timeout=0.5, attempts=2)
        assert result["result"] == "ok"
        await runner.stop()

    asyncio.run(_run())


def test_allowlist_matching(tmp_path):
    cmd_path = tmp_path / "echoer.py"
    cmd_path.write_text("import sys, json;\nprint(json.dumps({'result':'ok'}))", encoding="utf-8")
    async def _run_allow():
        runner = SubprocessStdioRunner(sys.executable, args=[str(cmd_path)], allowed_commands=[str(sys.executable)])
        await runner.start()
        await runner.stop()

    asyncio.run(_run_allow())

    async def _run_deny():
        runner = SubprocessStdioRunner("/not/allowed/python", args=[str(cmd_path)], allowed_commands=["other"])
        with pytest.raises(StartupError):
            await runner.start()

    asyncio.run(_run_deny())

    async def _run_case_insensitive():
        runner = SubprocessStdioRunner(sys.executable, args=[str(cmd_path)], allowed_commands=[os.path.basename(sys.executable).upper()])
        await runner.start()
        await runner.stop()

    asyncio.run(_run_case_insensitive())
