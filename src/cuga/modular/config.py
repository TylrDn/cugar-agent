from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal, Optional

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class AgentConfig:
    """Runtime configuration for planner/executor stacks."""

    profile: str = "demo_power"
    strategy: Literal["react", "plan_execute"] = "react"
    max_steps: int = 6
    temperature: float = 0.3
    observability: bool = True
    telemetry_opt_in: bool = False
    vector_backend: str = "local"
    rag_enabled: bool = False
    langfuse_host: Optional[str] = None

    @classmethod
    def from_env(cls) -> "AgentConfig":
        import os

        max_steps = _parse_int("PLANNER_MAX_STEPS", default=6, min_value=1, max_value=50)
        temperature = _parse_float("MODEL_TEMPERATURE", default=0.3, min_value=0.0, max_value=2.0)

        return cls(
            profile=os.getenv("PROFILE", "demo_power"),
            strategy=os.getenv("PLANNER_STRATEGY", "react"),
            max_steps=max_steps,
            temperature=temperature,
            observability=os.getenv("OBSERVABILITY_ENABLED", "true").lower() == "true",
            telemetry_opt_in=os.getenv("TELEMETRY_OPT_IN", "false").lower() == "true",
            vector_backend=os.getenv("VECTOR_BACKEND", "local"),
            rag_enabled=os.getenv("RAG_ENABLED", "false").lower() == "true",
            langfuse_host=os.getenv("LANGFUSE_HOST"),
        )


def _parse_int(key: str, default: int, min_value: int, max_value: int) -> int:
    import os

    raw = os.getenv(key)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        LOGGER.warning("Invalid int for %s; using default %s", key, default)
        return default
    clamped = max(min_value, min(value, max_value))
    if clamped != value:
        LOGGER.warning("Clamped %s from %s to %s", key, value, clamped)
    return clamped


def _parse_float(key: str, default: float, min_value: float, max_value: float) -> float:
    import os

    raw = os.getenv(key)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        LOGGER.warning("Invalid float for %s; using default %s", key, default)
        return default
    clamped = max(min_value, min(value, max_value))
    if clamped != value:
        LOGGER.warning("Clamped %s from %s to %s", key, value, clamped)
    return clamped
