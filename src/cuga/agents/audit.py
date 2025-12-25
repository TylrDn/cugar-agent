"""Audit helpers and constants."""

from __future__ import annotations

import json
from enum import Enum
from typing import Any

AUDIT_LOGGER_NAME = "cuga.audit"


class AuditEvent(str, Enum):
    CONTROLLER_RUN = "controller.run"
    TOOL_INVOCATION = "tool_invocation"


class AuditOutcome(str, Enum):
    SUCCESS = "success"
    ERROR = "error"


class AuditPolicy(str, Enum):
    ALLOW = "allow"


AUDIT_FIELD_EVENT = "event"
AUDIT_FIELD_PROFILE = "profile"
AUDIT_FIELD_GOAL = "goal"
AUDIT_FIELD_POLICY = "policy"
AUDIT_FIELD_TOOL = "tool"
AUDIT_FIELD_INPUT = "input"
AUDIT_FIELD_OUTCOME = "outcome"
AUDIT_FIELD_ERROR = "error"

AUDIT_EVENT_CONTROLLER_RUN = AuditEvent.CONTROLLER_RUN.value
AUDIT_EVENT_TOOL_INVOCATION = AuditEvent.TOOL_INVOCATION.value
AUDIT_OUTCOME_SUCCESS = AuditOutcome.SUCCESS.value
AUDIT_OUTCOME_ERROR = AuditOutcome.ERROR.value
AUDIT_POLICY_ALLOW = AuditPolicy.ALLOW.value

AUDIT_ERROR_REASON = "tool_execution_failed"

SENSITIVE_KEYS = {"password", "token", "secret", "api_key", "apikey", "authorization", "auth"}


def _truncate(value: str, max_length: int) -> str:
    if len(value) <= max_length:
        return value
    return value[:max_length] + "... [truncated]"


def _looks_sensitive(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return normalized in SENSITIVE_KEYS


def _summarize(value: Any, max_length: int) -> Any:
    if value is None or isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, str):
        return _truncate(value, max_length)
    if isinstance(value, dict):
        summary: dict[str, Any] = {}
        for key, nested in value.items():
            if _looks_sensitive(str(key)):
                summary[str(key)] = "<redacted>"
            else:
                summary[str(key)] = _summarize(nested, max_length // 2)
        return summary
    if isinstance(value, list):
        summarized = [_summarize(item, max_length // 2) for item in value[:5]]
        if len(value) > 5:
            summarized.append("<truncated>")
        return summarized
    try:
        json.dumps(value)
        return value
    except TypeError:
        return f"<{value.__class__.__name__}>"


def sanitize_for_audit(value: Any, *, max_length: int = 120) -> Any:
    """Return a non-sensitive summary suitable for audit logging."""

    return _summarize(value, max_length)
