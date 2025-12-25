from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

import httpx
import yaml

from .runner import MCPRunner
from .types import MCPRegistry, MCPServer, MCPTool

logger = logging.getLogger(__name__)

OpenAPIFetcher = Callable[[str], Dict[str, Any]]


class OpenAPISchemaCache:
    """Simple in-memory cache keyed by schema URL."""

    def __init__(self) -> None:
        self._cache: Dict[str, Dict[str, Any]] = {}

    def get(self, url: str, fetcher: OpenAPIFetcher) -> Dict[str, Any]:
        if url not in self._cache:
            self._cache[url] = fetcher(url)
        return self._cache[url]


def _bool_from_env(env_var: Optional[str], fallback: bool) -> bool:
    if env_var is None:
        return fallback
    value = os.getenv(env_var)
    if value is None:
        return fallback
    return value.lower() in {"1", "true", "yes", "on"}


def fetch_openapi_schema(schema_url: str) -> Dict[str, Any]:
    logger.info("Fetching OpenAPI schema from %s", schema_url)
    with httpx.Client() as client:
        response = client.get(schema_url, timeout=10.0)
        response.raise_for_status()
        return response.json()


def _resolve_operation(schema: Dict[str, Any], operation_id: str) -> tuple[str, str]:
    paths: Dict[str, Any] = schema.get("paths", {})
    for path, methods in paths.items():
        for method, definition in methods.items():
            if isinstance(definition, dict) and definition.get("operationId") == operation_id:
                return method.upper(), path
    raise KeyError(f"operationId '{operation_id}' not found in schema")


def _load_tools(
    server_name: str,
    server_cfg: Dict[str, Any],
    schema: Dict[str, Any],
) -> List[MCPTool]:
    tools: List[MCPTool] = []
    for entry in server_cfg.get("tools", []):
        enabled = _bool_from_env(entry.get("enabled_env"), entry.get("enabled", True))
        if not enabled:
            continue
        try:
            method = entry.get("method")
            path = entry.get("path")
            if entry.get("operation_id"):
                method, path = _resolve_operation(schema, entry["operation_id"])
            elif not (method and path):
                raise ValueError("Either operation_id or method+path must be provided for MCP tool")
            tools.append(
                MCPTool(
                    capability=entry.get("capability", server_name),
                    action=entry.get("action", entry.get("operation_id", "invoke")),
                    operation_id=entry.get("operation_id", f"{server_name}:{entry.get('action','invoke')}").strip(),
                    method=method.upper(),
                    path=path,
                    server=server_name,
                    base_url=server_cfg["url"],
                    description=entry.get("description", ""),
                    timeout=float(entry.get("timeout", server_cfg.get("timeout", 30.0))),
                    cost=float(entry.get("cost", 1.0)),
                    latency=float(entry.get("latency", 1.0)),
                    enabled=enabled,
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Skipping MCP tool on server %s: %s", server_name, exc)
    return tools


def load_registry(
    path: str | Path = "registry.yaml",
    *,
    fetcher: OpenAPIFetcher = fetch_openapi_schema,
    cache: Optional[OpenAPISchemaCache] = None,
) -> MCPRegistry:
    registry_path = Path(path)
    if not registry_path.exists():
        logger.info("Registry file %s not found; returning empty registry", registry_path)
        return MCPRegistry()

    data = yaml.safe_load(registry_path.read_text()) or {}
    servers_cfg: Dict[str, Any] = data.get("servers", {})
    cache = cache or OpenAPISchemaCache()

    servers: List[MCPServer] = []
    for server_name, cfg in servers_cfg.items():
        enabled = _bool_from_env(cfg.get("enabled_env"), cfg.get("enabled", True))
        if not enabled:
            logger.info("Skipping MCP server %s (disabled)", server_name)
            continue
        schema_url = cfg.get("schema") or cfg.get("openapi") or f"{cfg['url'].rstrip('/')}/openapi.json"
        schema = cache.get(schema_url, fetcher)
        tools = _load_tools(server_name, cfg, schema)
        servers.append(
            MCPServer(
                name=server_name,
                url=cfg["url"],
                schema_url=schema_url,
                enabled=enabled,
                enabled_env=cfg.get("enabled_env"),
                headers=cfg.get("headers", {}),
                tools=tools,
            )
        )
    return MCPRegistry(servers=servers)


def register_tools(
    registry: "ToolRegistry",  # type: ignore[FWDREF]
    mcp_registry: MCPRegistry,
    runner: Optional[MCPRunner] = None,
    *,
    profile: str = "default",
) -> None:
    """Register MCP tools into the provided ToolRegistry."""

    runner = runner or MCPRunner()
    for tool in mcp_registry.tools():
        name = tool.display_name

        def _handler(
            payload: Dict[str, Any], *, config: Dict[str, Any] | None = None, context: Any | None = None, _tool: MCPTool = tool, _name: str = name
        ) -> Any:
            merged_payload: Dict[str, Any] = {}
            merged_payload.update(config or {})
            merged_payload.update(payload or {})
            result = runner.invoke(_tool, merged_payload, headers=None)
            if not result.ok:
                raise RuntimeError(f"MCP invocation failed for {_name}")
            return result.output

        registry.register(
            profile,
            name,
            _handler,
            config={},
            cost=tool.cost,
            latency=tool.latency,
            description=tool.description or f"{tool.capability} capability ({tool.action})",
        )


__all__ = [
    "OpenAPIFetcher",
    "OpenAPISchemaCache",
    "fetch_openapi_schema",
    "load_registry",
    "register_tools",
]
