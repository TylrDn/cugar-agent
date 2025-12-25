from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional


Handler = Callable[[Dict[str, Any], Dict[str, Any]], Any]


@dataclass
class ToolSpec:
    name: str
    description: str
    handler: Handler
    parameters: Optional[Dict[str, Any]] = None


class ToolRegistry:
    def __init__(self, tools: Optional[Iterable[ToolSpec]] = None) -> None:
        self.tools: List[ToolSpec] = list(tools or [])

    def register(self, tool: ToolSpec) -> None:
        self.tools.append(tool)

    def get(self, name: str) -> Optional[ToolSpec]:
        return next((tool for tool in self.tools if tool.name == name), None)

    @classmethod
    def from_config(cls, config: List[Dict[str, Any]]) -> "ToolRegistry":
        registry_tools = []
        for entry in config:
            module_path = entry.get("module")
            handler = _load_handler(module_path) if module_path else None
            registry_tools.append(
                ToolSpec(
                    name=entry["name"],
                    description=entry.get("description", ""),
                    handler=handler or (lambda inputs, ctx: inputs),
                    parameters=entry.get("parameters"),
                )
            )
        return cls(registry_tools)


def _load_handler(module_path: str) -> Handler:
    module_name, _, attr = module_path.rpartition(".")
    module = __import__(module_name, fromlist=[attr])
    return getattr(module, attr)


def echo(inputs: Dict[str, Any], _: Dict[str, Any]) -> str:
    return inputs.get("text", "")
