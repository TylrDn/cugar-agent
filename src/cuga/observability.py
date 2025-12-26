"""Lightweight observability helpers that stay offline-friendly."""
from __future__ import annotations

import contextvars
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List

trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="")


@dataclass
class Span:
    name: str
    trace_id: str
    start_time: float = field(default_factory=time.time)
    attributes: Dict[str, Any] = field(default_factory=dict)

    def end(self, **attrs: Any) -> None:
        self.attributes.update(attrs)


class InMemoryTracer:
    def __init__(self) -> None:
        self.spans: List[Span] = []

    def start_span(self, name: str, **attributes: Any) -> Span:
        tid = trace_id_var.get() or attributes.get("trace_id") or ""
        span = Span(name=name, trace_id=tid, attributes=_redact(attributes))
        self.spans.append(span)
        return span


def _redact(data: Dict[str, Any]) -> Dict[str, Any]:
    lowered = {k.lower(): v for k, v in data.items()}
    redacted = {}
    for key, value in data.items():
        if any(s in key.lower() for s in {"secret", "token", "password"}):
            redacted[key] = "[redacted]"
        elif isinstance(value, dict):
            redacted[key] = _redact(value)
        else:
            redacted[key] = value
    return redacted


def propagate_trace(trace_id: str) -> None:
    trace_id_var.set(trace_id)
