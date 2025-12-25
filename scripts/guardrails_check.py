from __future__ import annotations

from pathlib import Path

"""Validate AGENTS.md guardrail anchors/phrases.

This script is part of the governance framework that treats AGENTS.md as code-as-policy
and ensures changes evolve alongside automated enforcement.
"""

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


def main() -> None:
    content = Path("AGENTS.md").read_text(encoding="utf-8")
    missing = [anchor for anchor in ANCHORS if anchor not in content]
    if missing:
        raise SystemExit(f"Missing anchors: {missing}")
    required_phrases = [
        "cuga.modular.tools.",
        "round-robin",
        "PLANNER_MAX_STEPS",
        "MODEL_TEMPERATURE",
    ]
    for phrase in required_phrases:
        if phrase not in content:
            raise SystemExit(f"Missing guardrail phrase: {phrase}")


if __name__ == "__main__":
    main()
