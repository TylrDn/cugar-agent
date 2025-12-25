"""Hydra/OmegaConf-driven MCP registry loader (vertical slice)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from omegaconf import DictConfig, OmegaConf

from .config_loader import load_registry_config
from .errors import RegistryMergeError, RegistryValidationError
from .models import MCPServerDefinition, MCPToolDefinition
from .snapshot import RegistrySnapshot

ENV_REGISTRY_PATH = "CUGA_MCP_REGISTRY_PATH"
_BOOL_TRUE = {"1", "true", "yes", "on"}


def _coerce_bool(value: Any, *, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in _BOOL_TRUE
    raise RegistryValidationError(f"Expected boolean or string flag, got {type(value).__name__}")


def _env_enabled(entry: Mapping[str, Any], env: Mapping[str, str], *, default: bool = True) -> bool:
    config_enabled = _coerce_bool(entry.get("enabled"), default=default)
    env_key = entry.get("enabled_env")
    if env_key is not None:
        env_val = env.get(env_key)
        if env_val is not None:
            return env_val.strip().lower() in _BOOL_TRUE

    return config_enabled


def _parse_tool(name: str, raw: Mapping[str, Any], env: Mapping[str, str]) -> MCPToolDefinition:
    if not isinstance(raw, Mapping):
        raise RegistryValidationError(f"Tool '{name}' must be a mapping")
    enabled = _env_enabled(raw, env)
    operation_id = raw.get("operation_id")
    if operation_id is not None and not isinstance(operation_id, str):
        raise RegistryValidationError(f"Tool '{name}' operation_id must be a string when provided")
    method = raw.get("method")
    if method is not None and not isinstance(method, str):
        raise RegistryValidationError(f"Tool '{name}' method must be a string when provided")
    path = raw.get("path")
    if path is not None and not isinstance(path, str):
        raise RegistryValidationError(f"Tool '{name}' path must be a string when provided")
    if operation_id is None and (method is None or path is None):
        raise RegistryValidationError(
            f"Tool '{name}' must provide an operation_id or both method and path",
        )
    return MCPToolDefinition(
        name=name,
        description=raw.get("description"),
        operation_id=operation_id,
        method=method.upper() if isinstance(method, str) else method,
        path=path,
        schema=raw.get("schema"),
        enabled=enabled,
        enabled_env=raw.get("enabled_env"),
    )


def _parse_server(name: str, raw: Mapping[str, Any], env: Mapping[str, str]) -> MCPServerDefinition:
    if not isinstance(raw, Mapping):
        raise RegistryValidationError(f"Server '{name}' must be a mapping")
    enabled = _env_enabled(raw, env)
    url = raw.get("url")
    if not isinstance(url, str) or not url.strip():
        raise RegistryValidationError(f"Server '{name}' must declare a non-empty url")
    tools_raw = raw.get("tools", [])
    if tools_raw is None:
        tools_raw = []
    if not isinstance(tools_raw, Sequence) or isinstance(tools_raw, (str, bytes)):
        raise RegistryValidationError(f"Server '{name}' tools must be a list")
    parsed_tools = tuple(
        _parse_tool(
            tool.get("name", f"{name}:{idx}") if isinstance(tool, Mapping) else f"{name}:{idx}",
            tool,
            env,
        )
        for idx, tool in enumerate(tools_raw)
    )
    return MCPServerDefinition(
        name=name,
        url=url,
        schema=raw.get("schema"),
        enabled=enabled,
        enabled_env=raw.get("enabled_env"),
        tools=tuple(tool for tool in parsed_tools if tool.enabled),
    )


def _merge_servers(documents: Iterable[tuple[Path, Mapping[str, Any]]], env: Mapping[str, str]) -> tuple[MCPServerDefinition, ...]:
    merged: list[MCPServerDefinition] = []
    seen: dict[str, Path] = {}
    for source_path, document in documents:
        if isinstance(document, DictConfig):
            document = OmegaConf.to_container(document, resolve=True)  # type: ignore[assignment]
        servers_block = document.get("servers", {})
        if servers_block is None:
            continue
        if not isinstance(servers_block, Mapping):
            raise RegistryValidationError(f"servers block in {source_path} must be a mapping")
        for name, raw_server in servers_block.items():
            server = _parse_server(name, raw_server, env)
            if server.enabled:
                if name in seen:
                    raise RegistryMergeError(
                        f"Duplicate server '{name}' in {source_path} conflicts with entry from {seen[name]}",
                    )
                merged.append(server)
                seen[name] = source_path
    return tuple(merged)


def load_mcp_registry_snapshot(
    path: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> RegistrySnapshot:
    """Load and validate an MCP registry snapshot.

    No network access or runtime bindings are performed in this slice.
    """

    env = env or os.environ
    raw_path = path if path is not None else env.get(ENV_REGISTRY_PATH)
    if not raw_path:
        return RegistrySnapshot.empty()
    resolved_path = Path(raw_path).expanduser().resolve()
    documents = load_registry_config(resolved_path)
    servers = _merge_servers(documents, env)
    sources = tuple(path for path, _ in documents)
    return RegistrySnapshot(servers=servers, sources=sources)


__all__ = [
    "ENV_REGISTRY_PATH",
    "load_mcp_registry_snapshot",
]
