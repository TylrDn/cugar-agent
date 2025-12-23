from __future__ import annotations

from importlib import metadata
from typing import Dict, Optional

from packaging.version import Version, parse

from cuga.mcp.config import MCPConfig, load_config
from cuga.mcp.interfaces import Registry, ToolSpec


class MCPRegistry(Registry):
    def __init__(self, config: Optional[MCPConfig] = None):
        self.config = config or load_config()
        self._tools: Dict[str, ToolSpec] = {alias: spec for alias, spec in self.config.tools.items()}

    def get(self, name: str, version: Optional[str] = None) -> ToolSpec:
        spec = self._tools.get(name)
        if spec is None:
            raise KeyError(f"Unknown MCP tool '{name}'")
        if version and spec.version:
            if Version(spec.version) != parse(version):
                raise ValueError(f"Tool {name} version mismatch: {spec.version} != {version}")
        return spec

    def list(self) -> list[ToolSpec]:
        return list(self._tools.values())

    def reload(self, config: Optional[MCPConfig] = None) -> None:
        self.config = config or load_config()
        self._tools = {alias: spec for alias, spec in self.config.tools.items()}

    def discover_entrypoints(self, group: str = "cuga_mcp_servers") -> None:
        try:
            entries = metadata.entry_points().select(group=group)
        except Exception:
            return
        for ep in entries:
            loader = ep.load()
            tool_spec: ToolSpec = loader()
            self._tools[tool_spec.alias] = tool_spec
