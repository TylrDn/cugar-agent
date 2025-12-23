from __future__ import annotations

import asyncio
import json
import os
import random
import signal
from asyncio.subprocess import Process
from typing import List, Optional

from cuga.mcp.errors import CallTimeout, StartupError
from cuga.mcp.interfaces import Runner
from cuga.mcp.telemetry.logging import setup_json_logging

LOGGER = setup_json_logging()


class SubprocessStdioRunner(Runner):
    def __init__(
        self,
        command: str,
        args: Optional[List[str]] = None,
        env: Optional[dict] = None,
        working_dir: Optional[str] = None,
        startup_timeout: float = 10.0,
        max_restarts: int = 2,
    ) -> None:
        self.command = command
        self.args = args or []
        self.env = env or {}
        self.working_dir = working_dir
        self.startup_timeout = startup_timeout
        self.max_restarts = max_restarts
        self.process: Optional[Process] = None
        self.restarts = 0

    async def start(self) -> None:
        if self.process and self.process.returncode is None:
            return
        if self.restarts > self.max_restarts:
            raise StartupError("Exceeded restart budget")
        self.restarts += 1
        self.process = await asyncio.create_subprocess_exec(
            self.command,
            *self.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, **self.env},
            cwd=self.working_dir,
        )
        await self._wait_for_ready()

    async def _wait_for_ready(self) -> None:
        await asyncio.sleep(0.1)
        if not self.process or self.process.returncode is not None:
            raise StartupError("Process failed to start")

    async def stop(self) -> None:
        if not self.process:
            return
        if self.process.returncode is None:
            self.process.send_signal(signal.SIGTERM)
            try:
                await asyncio.wait_for(self.process.wait(), timeout=3)
            except asyncio.TimeoutError:
                self.process.kill()
        self.process = None

    def is_healthy(self) -> bool:
        return bool(self.process and self.process.returncode is None)

    async def request(self, payload: dict, timeout: float) -> dict:
        if not self.process or not self.process.stdin or not self.process.stdout:
            raise CallTimeout("Process not running")
        message = json.dumps(payload) + "\n"
        self.process.stdin.write(message.encode())
        await self.process.stdin.drain()
        try:
            raw = await asyncio.wait_for(self.process.stdout.readline(), timeout=timeout)
        except asyncio.TimeoutError as exc:
            raise CallTimeout("MCP call timed out") from exc
        if not raw:
            raise CallTimeout("No response from MCP server")
        return json.loads(raw.decode())

    async def call_with_retry(self, payload: dict, timeout: float, attempts: int = 3) -> dict:
        for attempt in range(1, attempts + 1):
            try:
                return await self.request(payload, timeout)
            except CallTimeout:
                if attempt == attempts:
                    raise
                await asyncio.sleep(min(0.5 * (2 ** (attempt - 1)), 2.0) + random.random() * 0.1)
        raise CallTimeout("Retries exhausted")
