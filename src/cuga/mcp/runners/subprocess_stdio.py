from __future__ import annotations

# REVIEW-FIX: Subprocess taxonomy, allowlist, retries, and cross-platform safety.

import asyncio
import json
import os
import random
import signal
from asyncio.subprocess import Process
from collections.abc import Iterable
from typing import List, Optional

from cuga.mcp.errors import CallTimeout, StartupError
from cuga.mcp.interfaces import Runner
from cuga.mcp.telemetry.logging import setup_json_logging

LOGGER = setup_json_logging()

try:  # Windows friendly flag (no-op elsewhere)
    from subprocess import CREATE_NO_WINDOW
except ImportError:  # pragma: no cover - non-Windows
    CREATE_NO_WINDOW = 0


def _strip_exe(name: str) -> str:
    lower = name.lower()
    if lower.endswith(".exe"):
        return name[: -len(".exe")]
    return name


def _command_is_allowed(command: str, allowlist: Optional[Iterable[str]]) -> bool:
    if allowlist is None:
        return True
    # REVIEW-FIX: precedence = absolute match > basename (case preserving) > legacy case-insensitive basename.
    command_abs = os.path.abspath(command)
    command_abs_stripped = _strip_exe(os.path.normpath(command_abs))
    basename = _strip_exe(os.path.basename(command))
    legacy_basename = basename.lower()

    candidates = list(allowlist)

    for entry in candidates:
        if os.path.isabs(entry):
            normalized = _strip_exe(os.path.normpath(os.path.abspath(entry)))
            if command_abs_stripped == normalized:
                return True
    for entry in candidates:
        if _strip_exe(os.path.basename(entry)) == basename:
            return True
    for entry in candidates:
        if _strip_exe(os.path.basename(entry)).lower() == legacy_basename:
            return True
    return False


class SubprocessStdioRunner(Runner):
    def __init__(
        self,
        command: str,
        args: Optional[List[str]] = None,
        env: Optional[dict] = None,
        working_dir: Optional[str] = None,
        startup_timeout: float = 10.0,
        max_restarts: int = 2,
        allowed_commands: Optional[Iterable[str]] = None,
    ) -> None:
        self.command = command
        self.args = args or []
        self.env = env or {}
        self.working_dir = working_dir
        self.startup_timeout = startup_timeout
        self.max_restarts = max_restarts
        self.allowed_commands = list(allowed_commands) if allowed_commands is not None else None
        self.process: Optional[Process] = None
        self.restarts = 0
        self._ready = False

    async def start(self) -> None:
        if not _command_is_allowed(self.command, self.allowed_commands):
            raise StartupError("Command not allowed by MCPConfig.allow_commands")
        if self.process and self.process.returncode is None:
            return
        if self.restarts > self.max_restarts:
            raise StartupError("Exceeded restart budget")
        self.restarts += 1
        creationflags = CREATE_NO_WINDOW if CREATE_NO_WINDOW else 0
        try:
            self.process = await asyncio.create_subprocess_exec(
                self.command,
                *self.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, **self.env},
                cwd=self.working_dir,
                close_fds=True,
                creationflags=creationflags,
            )
        except FileNotFoundError as exc:  # REVIEW-FIX: classify spawn failures as startup
            raise StartupError("Process failed to start") from exc
        try:
            await self._wait_for_ready()
        except Exception:
            await self.stop()
            raise

    async def _wait_for_ready(self) -> None:
        if not self.process or self.process.returncode is not None:
            raise StartupError("Process failed to start")
        if not self.process.stdin or not self.process.stdout:
            raise StartupError("Missing stdio pipes")
        handshake = json.dumps({"method": "health", "params": {}}) + "\n"
        self.process.stdin.write(handshake.encode("utf-8"))
        await self.process.stdin.drain()
        try:
            raw = await asyncio.wait_for(self.process.stdout.readline(), timeout=self.startup_timeout)
        except asyncio.TimeoutError as exc:
            raise StartupError("Process failed to start") from exc
        if not raw:
            raise StartupError("EOF before handshake")
        try:
            json.loads(raw.decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            raise StartupError("Invalid JSON from MCP server") from exc
        self._ready = True

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
        self._ready = False

    def is_healthy(self) -> bool:
        return bool(self.process and self.process.returncode is None)

    async def request(self, payload: dict, timeout: float) -> dict:
        if not self.process or self.process.returncode is not None:
            raise StartupError("Process not running")
        if not self.process.stdin or not self.process.stdout:
            raise StartupError("Process missing stdio")
        message = json.dumps(payload) + "\n"
        self.process.stdin.write(message.encode("utf-8"))
        await self.process.stdin.drain()
        try:
            raw = await asyncio.wait_for(self.process.stdout.readline(), timeout=timeout)
        except asyncio.TimeoutError as exc:
            raise CallTimeout("MCP call timed out") from exc
        if not raw:
            raise StartupError("EOF before handshake")
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            raise StartupError("Invalid JSON from MCP server") from exc

    async def call_with_retry(self, payload: dict, timeout: float, attempts: int = 3) -> dict:
        last_error: Exception | None = None
        original_startup: StartupError | None = None
        for attempt in range(1, attempts + 1):
            try:
                return await self.request(payload, timeout)
            except CallTimeout as exc:
                last_error = exc
                if attempt == attempts:
                    raise
                await asyncio.sleep(min(0.5 * (2 ** (attempt - 1)), 2.0) + random.random() * 0.1)
            except StartupError as exc:
                if original_startup is None:
                    original_startup = exc
                last_error = exc
                await self.stop()
                await self.start()
                if attempt == attempts:
                    raise original_startup
        raise StartupError(str(last_error) if last_error else "Retries exhausted")
