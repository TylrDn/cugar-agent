from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class LLM(Protocol):
    def generate(self, prompt: str, temperature: float = 0.0) -> str:
        ...


@dataclass
class MockLLM:
    """Deterministic offline LLM for testing and planning."""

    def generate(self, prompt: str, temperature: float = 0.0) -> str:  # noqa: ARG002
        return "\n".join(line.strip() for line in prompt.splitlines() if line.strip())
