"""Profile-scoped policy enforcement for planner/executor flows."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping

import yaml

from .planner import PlanStep

DEFAULT_POLICY_DIR = Path(__file__).resolve().parents[3] / "configurations" / "policies"


@dataclass
class ToolPolicy:
    """Policy constraints for a single tool."""

    input_schema: Dict[str, Any] | None = None
    metadata_schema: Dict[str, Any] | None = None


@dataclass
class ProfilePolicy:
    """Resolved policy document for a profile."""

    profile: str
    allow_unknown_tools: bool
    metadata_schema: Dict[str, Any] | None
    allowed_tools: Dict[str, ToolPolicy]


@dataclass
class PolicyViolation(Exception):
    """Structured error raised when policy checks fail."""

    profile: str
    tool: str | None
    code: str
    message: str
    details: Dict[str, Any] | None = None

    def __str__(self) -> str:  # pragma: no cover - repr handled by dataclass/Exception
        context = f"profile={self.profile!r}"
        if self.tool:
            context += f", tool={self.tool!r}"
        return f"{self.code}: {self.message} ({context})"


class PolicyEnforcer:
    """Load and evaluate policies against plan steps and metadata."""

    def __init__(self, policy_root: str | Path | None = None) -> None:
        self.policy_root = Path(policy_root or DEFAULT_POLICY_DIR)
        self._cache: Dict[str, ProfilePolicy] = {}

    def validate_metadata(self, profile: str, metadata: Mapping[str, Any] | None) -> None:
        """Validate execution metadata against the profile policy."""

        policy = self._load_policy(profile)
        if not policy.metadata_schema:
            return

        errors = self._validate_schema(metadata or {}, policy.metadata_schema)
        if errors:
            raise PolicyViolation(
                profile=profile,
                tool=None,
                code="metadata_validation_failed",
                message="Metadata failed policy validation",
                details={"errors": errors},
            )

    def validate_step(self, profile: str, step: PlanStep, metadata: Mapping[str, Any] | None = None) -> None:
        """Validate a step input and metadata for a given profile."""

        policy = self._load_policy(profile)
        tool_policy = policy.allowed_tools.get(step.tool)

        if tool_policy is None:
            if not policy.allow_unknown_tools:
                raise PolicyViolation(
                    profile=profile,
                    tool=step.tool,
                    code="tool_not_allowed",
                    message=f"Tool '{step.tool}' is not permitted for profile '{profile}'",
                    details={"allowed_tools": sorted(policy.allowed_tools.keys())},
                )
            tool_policy = ToolPolicy()

        if tool_policy.metadata_schema:
            metadata_errors = self._validate_schema(metadata or {}, tool_policy.metadata_schema)
            if metadata_errors:
                raise PolicyViolation(
                    profile=profile,
                    tool=step.tool,
                    code="metadata_validation_failed",
                    message="Metadata failed tool-specific policy validation",
                    details={"errors": metadata_errors},
                )
        elif policy.metadata_schema:
            self.validate_metadata(profile, metadata)

        if tool_policy.input_schema:
            input_errors = self._validate_schema(step.input or {}, tool_policy.input_schema)
            if input_errors:
                raise PolicyViolation(
                    profile=profile,
                    tool=step.tool,
                    code="input_validation_failed",
                    message=f"Input for tool '{step.tool}' failed validation",
                    details={"errors": input_errors},
                )

    def _load_policy(self, profile: str) -> ProfilePolicy:
        if profile in self._cache:
            return self._cache[profile]

        policy_path = self.policy_root / f"{profile}.yaml"
        if not policy_path.exists():
            policy_path = self.policy_root / "default.yaml"
            if not policy_path.exists():
                raise PolicyViolation(
                    profile=profile,
                    tool=None,
                    code="policy_not_found",
                    message=f"No policy file found for profile '{profile}' and default policy missing",
                )

        raw = yaml.safe_load(policy_path.read_text()) or {}
        allowed_tools: Dict[str, ToolPolicy] = {}
        for tool_name, tool_entry in (raw.get("allowed_tools") or {}).items():
            allowed_tools[str(tool_name)] = ToolPolicy(
                input_schema=tool_entry.get("input_schema") if tool_entry else None,
                metadata_schema=tool_entry.get("metadata_schema") if tool_entry else None,
            )

        parsed = ProfilePolicy(
            profile=str(raw.get("profile", profile)),
            allow_unknown_tools=bool(raw.get("allow_unknown_tools", False)),
            metadata_schema=raw.get("metadata_schema"),
            allowed_tools=allowed_tools,
        )
        self._cache[profile] = parsed
        return parsed

    def _validate_schema(self, payload: Mapping[str, Any], schema: Dict[str, Any]) -> list[str]:
        errors: list[str] = []
        properties: Dict[str, Dict[str, Any]] = schema.get("properties", {})
        required = set(schema.get("required", []) or [])
        additional_allowed = schema.get("additionalProperties", True)

        for key in required:
            if key not in payload:
                errors.append(f"Missing required field '{key}'")

        for key, value in payload.items():
            prop_schema = properties.get(key)
            if prop_schema:
                expected_type = prop_schema.get("type")
                if expected_type and not self._is_type(value, expected_type):
                    errors.append(
                        f"Field '{key}' expected type '{expected_type}' but received '{type(value).__name__}'"
                    )
            elif not additional_allowed:
                errors.append(f"Unexpected field '{key}' not allowed by schema")

        return errors

    def _is_type(self, value: Any, expected: str) -> bool:
        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "object": Mapping,
            "array": (list, tuple),
            "null": type(None),
        }
        python_type = type_map.get(expected)
        if python_type is None:
            return True
        return isinstance(value, python_type)
