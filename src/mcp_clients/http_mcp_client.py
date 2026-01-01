"""HTTP MCP Client for remote MCP servers.

This module provides a JSON-RPC over HTTP client for communicating with
remote MCP servers (e.g., Pipedream-hosted servers).

Features:
- Token injection via .env.mcp
- Dynamic tool discovery
- Structured timeout and retry mechanisms
- Comprehensive error handling
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class HttpMCPClient:
    """JSON-RPC over HTTP client for remote MCP servers.
    
    This client handles communication with remote MCP servers via HTTP/HTTPS,
    supporting authentication, retries, and timeouts.
    
    Attributes:
        base_url: Base URL of the remote MCP server
        timeout: Default timeout for requests in seconds
        max_retries: Maximum number of retry attempts
        headers: HTTP headers to include in requests
    """

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 30.0,
        max_retries: int = 3,
        auth_token: Optional[str] = None,
        env_file: str = ".env.mcp",
    ) -> None:
        """Initialize the HTTP MCP client.
        
        Args:
            base_url: Base URL of the MCP server
            timeout: Request timeout in seconds (default: 30.0)
            max_retries: Maximum retry attempts (default: 3)
            auth_token: Optional authentication token
            env_file: Path to .env file for token injection (default: .env.mcp)
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.headers: Dict[str, str] = {
            "Content-Type": "application/json",
        }
        
        # Load environment variables from .env.mcp
        if os.path.exists(env_file):
            load_dotenv(env_file)
            logger.info(f"Loaded environment from {env_file}")
        
        # Set auth token if provided or found in environment
        token = auth_token or os.getenv("MCP_AUTH_TOKEN")
        if token:
            self.headers["Authorization"] = f"Bearer {token}"
        
        self._client: Optional[httpx.Client] = None
        self._tools_cache: Optional[List[Dict[str, Any]]] = None

    def _get_client(self) -> httpx.Client:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout)
        return self._client

    async def discover_tools(self) -> List[Dict[str, Any]]:
        """Discover available tools from the MCP server.
        
        Returns:
            List of tool definitions with their schemas
            
        Raises:
            httpx.HTTPError: If the request fails
            ValueError: If the response is invalid
        """
        if self._tools_cache is not None:
            return self._tools_cache
        
        try:
            response = await self._call_jsonrpc(
                method="tools/list",
                params={},
            )
            
            if "tools" not in response:
                logger.warning("Invalid tools/list response: missing 'tools' field")
                return []
            
            self._tools_cache = response["tools"]
            logger.info(f"Discovered {len(self._tools_cache)} tools from {self.base_url}")
            return self._tools_cache
            
        except Exception as exc:
            logger.error(f"Failed to discover tools from {self.base_url}: {exc}")
            raise

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
            timeout: Optional override for request timeout
            
        Returns:
            Tool execution result
            
        Raises:
            httpx.HTTPError: If the request fails
            ValueError: If the response indicates an error
        """
        response = await self._call_jsonrpc(
            method="tools/call",
            params={
                "name": tool_name,
                "arguments": arguments,
            },
            timeout=timeout,
        )
        
        if "error" in response:
            error_msg = response["error"].get("message", "Unknown error")
            raise ValueError(f"Tool call failed: {error_msg}")
        
        return response.get("result", {})

    async def _call_jsonrpc(
        self,
        method: str,
        params: Dict[str, Any],
        *,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Make a JSON-RPC call to the MCP server.
        
        Args:
            method: JSON-RPC method name
            params: Method parameters
            timeout: Optional timeout override
            
        Returns:
            JSON-RPC response result
            
        Raises:
            httpx.HTTPError: If the request fails after all retries
            ValueError: If the response is invalid JSON-RPC
        """
        client = self._get_client()
        request_timeout = timeout or self.timeout
        
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params,
        }
        
        last_error: Optional[Exception] = None
        
        for attempt in range(self.max_retries):
            try:
                response = client.post(
                    f"{self.base_url}/jsonrpc",
                    json=payload,
                    headers=self.headers,
                    timeout=request_timeout,
                )
                response.raise_for_status()
                
                result = response.json()
                
                if "error" in result:
                    error_data = result["error"]
                    error_msg = error_data.get("message", "Unknown error")
                    error_code = error_data.get("code", -1)
                    raise ValueError(f"JSON-RPC error {error_code}: {error_msg}")
                
                return result.get("result", {})
                
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                if attempt < self.max_retries - 1:
                    backoff = min(2 ** attempt, 8)  # Exponential backoff, max 8s
                    logger.warning(
                        f"Request failed (attempt {attempt + 1}/{self.max_retries}), "
                        f"retrying in {backoff}s: {exc}"
                    )
                    import asyncio
                    await asyncio.sleep(backoff)
                else:
                    logger.error(f"Request failed after {self.max_retries} attempts: {exc}")
        
        if last_error:
            raise last_error
        
        raise RuntimeError("Unexpected error: no exception recorded")

    async def health_check(self) -> bool:
        """Check if the MCP server is healthy.
        
        Returns:
            True if server is healthy, False otherwise
        """
        try:
            await self._call_jsonrpc(
                method="health",
                params={},
                timeout=5.0,
            )
            return True
        except Exception as exc:
            logger.warning(f"Health check failed for {self.base_url}: {exc}")
            return False

    def close(self) -> None:
        """Close the HTTP client and release resources."""
        if self._client is not None:
            self._client.close()
            self._client = None
        logger.debug(f"Closed HTTP MCP client for {self.base_url}")

    async def __aenter__(self) -> "HttpMCPClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        self.close()
