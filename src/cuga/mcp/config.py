from __future__ import annotations

import os
import tomllib
from typing import Dict, Optional

from cuga.compat.pydantic_stub import BaseModel, Field, ValidationError

from cuga.mcp.interfaces import ToolSpec


class PoolConfig(BaseModel):
    name: str = "default"
    max_active: int = 4
    min_idle: int = 0
    idle_ttl_s: float = 30.0


class MCPConfig(BaseModel):
    default_transport: str = "stdio"
    allow_commands: list[str] = Field(default_factory=list)
    tools: Dict[str, ToolSpec] = Field(default_factory=dict)
    pools: Dict[str, PoolConfig] = Field(default_factory=dict)

    @classmethod
    def from_toml(cls, path: str) -> "MCPConfig":
        with open(path, "rb") as fh:
            raw = tomllib.load(fh)
        data = raw.get("mcp", {})
        # Inject alias into tool specs when missing
        tools_data = data.get("tools", {})
        normalized_tools = {}
        for alias, spec in tools_data.items():
            spec.setdefault("alias", alias)
            spec.setdefault("name", alias)
            normalized_tools[alias] = ToolSpec(**spec)
        data["tools"] = normalized_tools
        return cls.model_validate(data)


DEFAULT_CONFIG_PATHS = (
    os.getenv("CUGA_MCP_CONFIG"),
    os.path.join(os.getcwd(), "settings.mcp.toml"),
    os.path.join(os.path.dirname(__file__), "settings.toml"),
)


def load_config(explicit_path: Optional[str] = None) -> MCPConfig:
    paths = [explicit_path] if explicit_path else []
    paths.extend([p for p in DEFAULT_CONFIG_PATHS if p])
    for path in paths:
        if path and os.path.exists(path):
            try:
                return MCPConfig.from_toml(path)
            except ValidationError as exc:
                raise ValueError(f"Invalid MCP config at {path}: {exc}") from exc
    return MCPConfig()
