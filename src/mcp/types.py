from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MCPTool:
    """Represents a single MCP-exposed capability."""

    capability: str
    action: str
    operation_id: str
    method: str
    path: str
    server: str
    base_url: str = ""
    description: str = ""
    timeout: float = 30.0
    cost: float = 1.0
    latency: float = 1.0
    enabled: bool = True

    @property
    def display_name(self) -> str:
        return f"{self.capability} · {self.action}"


@dataclass
class MCPServer:
    """Configuration for an MCP server defined in the registry."""

    name: str
    url: str
    schema_url: str
    enabled: bool = True
    enabled_env: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    tools: List[MCPTool] = field(default_factory=list)


@dataclass
class MCPRegistry:
    """Collection of MCP servers and tools."""

    servers: List[MCPServer] = field(default_factory=list)

    def tools(self) -> List[MCPTool]:
        tools: List[MCPTool] = []
        for server in self.servers:
            tools.extend([tool for tool in server.tools if tool.enabled])
        return tools


@dataclass
class InvocationResult:
    ok: bool
    status_code: int
    output: Any
    raw: Any | None = None


class InvocationError(Exception):
    def __init__(self, message: str, *, status_code: Optional[int] = None, details: Any | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details

    def __str__(self) -> str:  # pragma: no cover - trivial formatting
        base = super().__str__()
        if self.status_code is not None:
            return f"{base} (status={self.status_code})"
        return base
