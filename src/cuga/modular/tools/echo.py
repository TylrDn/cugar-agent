from __future__ import annotations

from typing import Any, Dict

SCHEMA = {
    "name": "echo",
    "inputs": {"message": {"type": "string"}},
    "outputs": {"message": {"type": "string"}},
}


async def run(inputs: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    return {"echo": inputs.get("message"), "trace_id": context.get("trace_id")}
