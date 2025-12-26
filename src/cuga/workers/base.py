from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any, Dict

from cuga.sandbox.isolation import validate_tool_path


@dataclass
class Worker:
    name: str

    async def execute(self, step: Any, trace_id: str) -> Any:
        validate_tool_path(step.tool)
        module = importlib.import_module(step.tool)
        if not hasattr(module, "SCHEMA") or "inputs" not in module.SCHEMA:
            raise ValueError("Tool schema missing")
        expected = set(module.SCHEMA.get("inputs", {}).keys())
        missing = expected - set(step.params.keys())
        if missing:
            raise ValueError(f"Missing inputs: {missing}")
        return await module.run(step.params, {"trace_id": trace_id, "worker": self.name})
