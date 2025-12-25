from __future__ import annotations

from pathlib import Path

ANCHORS = [
    "## Design Tenets",
    "## Agent Roles & Interfaces",
    "## Planning Protocol",
    "## Tool Contract",
    "## Memory & RAG",
    "## Coordinator Policy",
    "## Configuration Policy",
    "## Observability & Tracing",
    "## Testing Invariants",
    "## Change Management",
]


def test_agents_md_contains_required_sections() -> None:
    content = Path("AGENTS.md").read_text(encoding="utf-8")
    for anchor in ANCHORS:
        assert anchor in content
    assert "cuga.modular.tools." in content
    assert "round-robin" in content
    assert "PLANNER_MAX_STEPS" in content
    assert "MODEL_TEMPERATURE" in content
