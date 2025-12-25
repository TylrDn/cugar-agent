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
