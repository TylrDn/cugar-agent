"""Profile-aware tool registry for subagent isolation."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Mapping

ToolCallable = Callable[..., Any]


@dataclass
class ToolRegistry:
    """Manages tool exposure per profile without cross-talk."""

    _tools: Dict[str, Dict[str, Dict[str, Any]]] = field(default_factory=dict)

    def register(self, profile: str, name: str, handler: ToolCallable, *, config: Mapping[str, Any] | None = None) -> None:
        profile_tools = self._tools.setdefault(profile, {})
        if name in profile_tools:
            raise ValueError(f"Tool '{name}' already registered for profile '{profile}'")
        profile_tools[name] = {"handler": handler, "config": dict(config or {})}

    def sandbox(self, profile: str) -> "ToolRegistry":
        """Return an isolated view for a single profile."""

        if profile not in self._tools:
            raise KeyError(f"Profile '{profile}' not found in registry")
        profile_tools = self._tools[profile]
        return ToolRegistry({profile: copy.deepcopy(profile_tools)})

    def resolve(self, profile: str, name: str) -> Dict[str, Any]:
        profile_tools = self._tools.get(profile, {})
        if name not in profile_tools:
            raise KeyError(f"Tool '{name}' not found for profile '{profile}'")
        return profile_tools[name]

    def tools_for_profile(self, profile: str) -> Dict[str, Dict[str, Any]]:
        return dict(self._tools.get(profile, {}))

    def merge(self, other: "ToolRegistry") -> "ToolRegistry":
        merged: Dict[str, Dict[str, Dict[str, Any]]] = {p: copy.deepcopy(t) for p, t in self._tools.items()}
        for profile, tools in other._tools.items():
            merged.setdefault(profile, {})
            for name, details in tools.items():
                if name in merged[profile]:
                    raise ValueError(f"Conflict registering tool '{name}' for profile '{profile}'")
                merged[profile][name] = copy.deepcopy(details)
        return ToolRegistry(merged)

    def profiles(self) -> set[str]:
        return set(self._tools.keys())
