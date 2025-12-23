from __future__ import annotations

# REVIEW-FIX: Registry reload atomicity and entry-point shims for 3.9-3.12.

from collections.abc import Iterable
from importlib_metadata import metadata
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
        if version:
            if not spec.version or Version(spec.version) != parse(version):
                raise ValueError(f"Tool {name} version mismatch: {spec.version} != {version}")
        return spec

    def list(self) -> list[ToolSpec]:
        return list(self._tools.values())

    def reload(self, config: Optional[MCPConfig] = None) -> None:
        new_config = config or load_config()
        self.config = new_config
        self._tools = {alias: spec for alias, spec in new_config.tools.items()}

    def _load_entrypoints(self, entries: Iterable[object]) -> None:
        for ep in entries:
            loader = ep.load()  # type: ignore[call-arg]
            tool_spec: ToolSpec = loader()
            self._tools[tool_spec.alias] = tool_spec

    def discover_entrypoints(self, group: str = "cuga_mcp_servers") -> None:
        try:
            eps = metadata.entry_points()
        except Exception:
            return
        entries = None
        if hasattr(eps, "select"):
            entries = eps.select(group=group)
        elif isinstance(eps, dict):
            entries = eps.get(group, [])
        elif isinstance(eps, Iterable):
            entries = [ep for ep in eps if getattr(ep, "group", None) == group]
        if entries is None:
            return
        self._load_entrypoints(entries)
