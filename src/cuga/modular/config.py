from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional


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

        return cls(
            profile=os.getenv("PROFILE", "demo_power"),
            strategy=os.getenv("PLANNER_STRATEGY", "react"),
            max_steps=int(os.getenv("PLANNER_MAX_STEPS", "6")),
            temperature=float(os.getenv("MODEL_TEMPERATURE", "0.3")),
            observability=os.getenv("OBSERVABILITY_ENABLED", "true").lower() == "true",
            telemetry_opt_in=os.getenv("TELEMETRY_OPT_IN", "false").lower() == "true",
            vector_backend=os.getenv("VECTOR_BACKEND", "local"),
            rag_enabled=os.getenv("RAG_ENABLED", "false").lower() == "true",
            langfuse_host=os.getenv("LANGFUSE_HOST"),
        )
