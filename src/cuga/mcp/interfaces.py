from __future__ import annotations

from typing import Any, Dict, Optional, Protocol

from pydantic import BaseModel, Field


class ToolRequest(BaseModel):
    method: str
    params: Dict[str, Any] = Field(default_factory=dict)
    timeout_s: Optional[float] = None


class ToolResponse(BaseModel):
    ok: bool
    result: Any | None = None
    error: str | None = None
    metrics: Dict[str, Any] = Field(default_factory=dict)


class MCPTool(Protocol):
    async def start(self) -> None:
        ...

    async def stop(self) -> None:
        ...

    async def call(self, req: ToolRequest) -> ToolResponse:
        ...


class Runner(Protocol):
    async def start(self) -> None:
        ...

    async def stop(self) -> None:
        ...

    def is_healthy(self) -> bool:
        ...


class Registry(Protocol):
    def get(self, name: str, version: Optional[str] = None) -> "ToolSpec":
        ...

    def list(self) -> list["ToolSpec"]:
        ...


class ToolSpec(BaseModel):
    alias: str
    name: str
    version: Optional[str] = None
    transport: str = "stdio"
    command: Optional[str] = None
    args: list[str] = Field(default_factory=list)
    env: Dict[str, str] = Field(default_factory=dict)
    capabilities: list[str] = Field(default_factory=list)
    working_dir: Optional[str] = None
    pool: Optional[str] = None
    timeout_s: float = 30.0
