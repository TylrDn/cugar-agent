from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class ToolSpec:
    name: str
    description: str = ""

class ToolRegistry:
    def __init__(self):
        self.tools: Dict[str, Any] = {}

    def register(self, name: str, tool: Any) -> None:
        self.tools[name] = tool

    def get(self, name: str) -> Any:
        return self.tools[name]

from .echo import SCHEMA, run  # noqa: E402,F401
