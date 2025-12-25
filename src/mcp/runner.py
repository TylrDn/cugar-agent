from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

from .types import InvocationError, InvocationResult, MCPTool

logger = logging.getLogger(__name__)


class MCPRunner:
    """Thin adapter for invoking MCP/OpenAPI tools."""

    def __init__(self, *, timeout: float = 15.0, retries: int = 1, client: Optional[httpx.Client] = None) -> None:
        self.timeout = timeout
        self.retries = retries
        self.client = client or httpx.Client()

    def _build_url(self, tool: MCPTool) -> str:
        if tool.path.startswith("http"):
            return tool.path
        base = tool.base_url.rstrip("/") if tool.base_url else tool.server.rstrip("/")
        return f"{base}{tool.path if tool.path.startswith('/') else '/' + tool.path}"

    def invoke(self, tool: MCPTool, payload: Dict[str, Any], *, headers: Optional[Dict[str, str]] = None) -> InvocationResult:
        url = self._build_url(tool)
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = self.client.request(
                    tool.method,
                    url,
                    json=payload,
                    headers=headers,
                    timeout=tool.timeout or self.timeout,
                )
                if response.status_code >= 500 and attempt < self.retries:
                    continue
                if response.is_success:
                    try:
                        body = response.json()
                    except Exception:  # noqa: BLE001
                        body = response.text
                    return InvocationResult(ok=True, status_code=response.status_code, output=body, raw=response)
                return InvocationResult(ok=False, status_code=response.status_code, output=response.text, raw=response)
            except httpx.HTTPError as exc:
                logger.warning("MCP invocation error for %s (attempt %s/%s): %s", tool.display_name, attempt + 1, self.retries + 1, exc)
                last_error = exc
        raise InvocationError(f"Failed to invoke {tool.display_name}", details=str(last_error))

    def close(self) -> None:
        try:
            self.client.close()
        except Exception:  # noqa: BLE001
            logger.debug("Ignoring MCP runner close failure", exc_info=True)


__all__ = ["MCPRunner"]
