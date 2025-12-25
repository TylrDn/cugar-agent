from __future__ import annotations

from cuga.modular.agents import WorkerAgent
from cuga.modular.memory import VectorMemory
from cuga.modular.tools import ToolRegistry, ToolSpec


def test_worker_defaults_to_memory_profile() -> None:
    registry = ToolRegistry([ToolSpec(name="echo", description="", handler=lambda i, c: c["profile"] + i.get("text", ""))])
    memory = VectorMemory(profile="memory_profile")
    worker = WorkerAgent(registry=registry, memory=memory)
    result = worker.execute([{"tool": "echo", "input": {"text": "!"}}])
    assert result.output == "memory_profile!"
