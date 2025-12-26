from __future__ import annotations

import os
from typing import Dict

ALLOWED_ENV_PREFIXES = ("AGENT_", "OTEL_", "LANGFUSE_", "OPENINFERENCE_", "TRACELOOP_")


def filter_env(env: Dict[str, str]) -> Dict[str, str]:
    return {k: v for k, v in env.items() if k.startswith(ALLOWED_ENV_PREFIXES)}


def validate_tool_path(path: str) -> None:
    if not path.startswith("cuga.modular.tools."):
        raise ValueError(f"Tool {path} is not allowlisted")


def budget_within_limits(spent: int, ceiling: int) -> bool:
    return spent <= ceiling
