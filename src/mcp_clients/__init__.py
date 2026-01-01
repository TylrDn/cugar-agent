"""MCP Client Abstractions for CUGA Agent.

This package provides client implementations for different MCP server transports:
- HTTP: JSON-RPC over HTTP for remote MCP servers
- Process: Subprocess-based stdio JSON-RPC for local MCP servers
- Embedded: Loader for embedded MCP servers within the cugar-agent repository
"""

from .embedded_mcp_loader import EmbeddedMCPLoader
from .http_mcp_client import HttpMCPClient
from .process_mcp_client import ProcessMCPClient

__all__ = [
    "HttpMCPClient",
    "ProcessMCPClient",
    "EmbeddedMCPLoader",
]
