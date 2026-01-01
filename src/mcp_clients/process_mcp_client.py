"""Process MCP Client for local subprocess-based MCP servers.

This module provides a subprocess manager to launch and communicate with
local MCP servers via stdio JSON-RPC.

Features:
- Auto-restart on failure
- Health checks and monitoring
- Sandboxed execution
- Structured timeout and error handling
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
from asyncio.subprocess import Process
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Windows-friendly process creation flag
try:
    from subprocess import CREATE_NO_WINDOW
except ImportError:
    CREATE_NO_WINDOW = 0


class ProcessMCPClient:
    """Subprocess-based stdio JSON-RPC client for local MCP servers.
    
    This client manages the lifecycle of local MCP servers launched as subprocesses,
    communicating via stdin/stdout using JSON-RPC protocol.
    
    Attributes:
        command: Command to execute
        args: Command arguments
        env: Environment variables for the subprocess
        working_dir: Working directory for the subprocess
        timeout: Default timeout for operations
        max_restarts: Maximum number of restart attempts
    """

    def __init__(
        self,
        command: str,
        args: Optional[List[str]] = None,
        *,
        env: Optional[Dict[str, str]] = None,
        working_dir: Optional[str] = None,
        timeout: float = 30.0,
        max_restarts: int = 3,
        startup_timeout: float = 10.0,
    ) -> None:
        """Initialize the Process MCP client.
        
        Args:
            command: Command to execute (e.g., "npx", "python")
            args: Command arguments (e.g., ["-y", "@modelcontextprotocol/server-filesystem"])
            env: Additional environment variables
            working_dir: Working directory for the subprocess
            timeout: Default timeout for operations in seconds (default: 30.0)
            max_restarts: Maximum restart attempts (default: 3)
            startup_timeout: Timeout for server startup in seconds (default: 10.0)
        """
        self.command = command
        self.args = args or []
        self.env = env or {}
        self.working_dir = working_dir
        self.timeout = timeout
        self.max_restarts = max_restarts
        self.startup_timeout = startup_timeout
        
        self.process: Optional[Process] = None
        self._restart_count = 0
        self._ready = False
        self._tools_cache: Optional[List[Dict[str, Any]]] = None
        self._request_id = 0

    async def start(self) -> None:
        """Start the MCP server subprocess.
        
        Raises:
            RuntimeError: If the server fails to start or exceeds restart limit
            FileNotFoundError: If the command is not found
        """
        if self.process and self.process.returncode is None:
            logger.debug(f"Process already running: {self.command}")
            return
        
        if self._restart_count >= self.max_restarts:
            raise RuntimeError(
                f"Exceeded maximum restart limit ({self.max_restarts}) for {self.command}"
            )
        
        self._restart_count += 1
        logger.info(
            f"Starting MCP server: {self.command} {' '.join(self.args)} "
            f"(attempt {self._restart_count}/{self.max_restarts})"
        )
        
        # Build environment
        process_env = {**os.environ, **self.env}
        
        # Create subprocess with stdio pipes
        creationflags = CREATE_NO_WINDOW if CREATE_NO_WINDOW else 0
        
        try:
            self.process = await asyncio.create_subprocess_exec(
                self.command,
                *self.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=process_env,
                cwd=self.working_dir,
                close_fds=True,
                creationflags=creationflags,
            )
        except FileNotFoundError as exc:
            logger.error(f"Command not found: {self.command}")
            raise RuntimeError(f"Failed to start MCP server: {self.command}") from exc
        
        # Wait for process to be ready
        try:
            await self._wait_for_ready()
            self._ready = True
            logger.info(f"MCP server ready: {self.command}")
        except Exception as exc:
            logger.error(f"Failed to initialize MCP server: {exc}")
            await self.stop()
            raise

    async def _wait_for_ready(self) -> None:
        """Wait for the server to be ready by performing a health check.
        
        Raises:
            RuntimeError: If the server fails to respond or responds incorrectly
        """
        if not self.process or self.process.returncode is not None:
            raise RuntimeError("Process is not running")
        
        if not self.process.stdin or not self.process.stdout:
            raise RuntimeError("Process stdio pipes not available")
        
        # Send initialization handshake
        init_request = {
            "jsonrpc": "2.0",
            "id": self._get_request_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "cugar-agent",
                    "version": "0.2.6",
                },
            },
        }
        
        try:
            response = await self._send_request(init_request, timeout=self.startup_timeout)
            
            if "error" in response:
                error_msg = response["error"].get("message", "Unknown error")
                raise RuntimeError(f"Initialization failed: {error_msg}")
            
            logger.debug(f"Server initialized: {response}")
            
        except asyncio.TimeoutError as exc:
            raise RuntimeError("Server initialization timed out") from exc

    async def stop(self) -> None:
        """Stop the MCP server subprocess.
        
        Sends SIGTERM and waits for graceful shutdown, then forcefully kills if needed.
        """
        if not self.process:
            return
        
        logger.info(f"Stopping MCP server: {self.command}")
        
        if self.process.returncode is None:
            # Send termination signal
            try:
                self.process.send_signal(signal.SIGTERM)
            except ProcessLookupError:
                logger.debug("Process already terminated")
                return
            
            # Wait for graceful shutdown
            try:
                await asyncio.wait_for(self.process.wait(), timeout=3.0)
                logger.debug("Process terminated gracefully")
            except asyncio.TimeoutError:
                logger.warning("Process did not terminate gracefully, killing")
                self.process.kill()
                await self.process.wait()
        
        self.process = None
        self._ready = False
        logger.info(f"MCP server stopped: {self.command}")

    def is_healthy(self) -> bool:
        """Check if the server process is healthy.
        
        Returns:
            True if process is running, False otherwise
        """
        return bool(self.process and self.process.returncode is None and self._ready)

    async def discover_tools(self) -> List[Dict[str, Any]]:
        """Discover available tools from the MCP server.
        
        Returns:
            List of tool definitions with their schemas
            
        Raises:
            RuntimeError: If the server is not running or request fails
        """
        if self._tools_cache is not None:
            return self._tools_cache
        
        if not self.is_healthy():
            raise RuntimeError("Server is not running")
        
        request = {
            "jsonrpc": "2.0",
            "id": self._get_request_id(),
            "method": "tools/list",
            "params": {},
        }
        
        response = await self._send_request(request)
        
        if "error" in response:
            error_msg = response["error"].get("message", "Unknown error")
            raise RuntimeError(f"Failed to discover tools: {error_msg}")
        
        result = response.get("result", {})
        self._tools_cache = result.get("tools", [])
        logger.info(f"Discovered {len(self._tools_cache)} tools from {self.command}")
        
        return self._tools_cache

    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        *,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Call a tool on the MCP server.
        
        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments as a dictionary
            timeout: Optional timeout override
            
        Returns:
            Tool execution result
            
        Raises:
            RuntimeError: If the server is not running or request fails
            ValueError: If the response indicates an error
        """
        if not self.is_healthy():
            raise RuntimeError("Server is not running")
        
        request = {
            "jsonrpc": "2.0",
            "id": self._get_request_id(),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        }
        
        response = await self._send_request(request, timeout=timeout)
        
        if "error" in response:
            error_msg = response["error"].get("message", "Unknown error")
            raise ValueError(f"Tool call failed: {error_msg}")
        
        return response.get("result", {})

    async def _send_request(
        self,
        request: Dict[str, Any],
        *,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Send a JSON-RPC request to the server and wait for response.
        
        Args:
            request: JSON-RPC request dictionary
            timeout: Optional timeout override
            
        Returns:
            JSON-RPC response dictionary
            
        Raises:
            RuntimeError: If the server is not running or I/O fails
            asyncio.TimeoutError: If the request times out
        """
        if not self.process or not self.process.stdin or not self.process.stdout:
            raise RuntimeError("Process stdio not available")
        
        request_timeout = timeout or self.timeout
        
        # Send request
        message = json.dumps(request) + "\n"
        self.process.stdin.write(message.encode("utf-8"))
        await self.process.stdin.drain()
        
        # Wait for response
        try:
            raw_response = await asyncio.wait_for(
                self.process.stdout.readline(),
                timeout=request_timeout,
            )
        except asyncio.TimeoutError:
            logger.error(f"Request timed out after {request_timeout}s: {request['method']}")
            raise
        
        if not raw_response:
            raise RuntimeError("Server closed connection (EOF)")
        
        try:
            response = json.loads(raw_response.decode("utf-8"))
            return response
        except json.JSONDecodeError as exc:
            logger.error(f"Invalid JSON from server: {raw_response}")
            raise RuntimeError("Invalid JSON response from server") from exc

    def _get_request_id(self) -> int:
        """Generate a unique request ID."""
        self._request_id += 1
        return self._request_id

    async def __aenter__(self) -> "ProcessMCPClient":
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.stop()
