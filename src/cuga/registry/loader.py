from __future__ import annotations

import copy
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List

try:
    import yaml
except Exception:
    yaml = None

from cuga.observability import InMemoryTracer


@dataclass(order=True)
class RegistryEntry:
    sort_index: tuple = field(init=False, repr=False)
    id: str
    ref: str
    sandbox: str
    enabled: bool = True
    tier: int = 1
    env: Dict[str, Any] = field(default_factory=dict)
    mounts: List[str] = field(default_factory=list)
    scopes: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.sort_index = (self.tier, self.id)


class Registry:
    def __init__(self, path: Path, tracer: InMemoryTracer | None = None) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
        self.tracer = tracer or InMemoryTracer()
        self._entries = self._load(self.path.read_text())

    @staticmethod
    def _load(content: str) -> List[RegistryEntry]:
        data = _safe_load(content)
        defaults = data.get("defaults", {})
        entries: List[RegistryEntry] = []
        for raw in data.get("entries", []):
            merged = copy.deepcopy(defaults)
            merged.update(raw)
            if merged.get("tier") == 2 and "enabled" not in raw:
                merged["enabled"] = False
            entry = RegistryEntry(
                id=merged["id"],
                ref=merged["ref"],
                sandbox=merged.get("sandbox", "py-slim"),
                enabled=merged.get("enabled", True),
                tier=merged.get("tier", 1),
                env=merged.get("env", {}),
                mounts=merged.get("mounts", []),
                scopes=merged.get("scopes", []),
            )
            entries.append(entry)
        return sorted(entries)

    @property
    def entries(self) -> List[RegistryEntry]:
        with self._lock:
            return list(self._entries)

    def hot_reload(self, content: str) -> None:
        new_entries = self._load(content)
        with self._lock:
            self._entries = new_entries
            self.tracer.start_span("registry.reload", trace_id="hot-reload").end(count=len(new_entries))

    def get_enabled(self) -> List[RegistryEntry]:
        return [e for e in self.entries if e.enabled]

    def pick(self, scope: str) -> Iterable[RegistryEntry]:
        for entry in self.get_enabled():
            if scope in entry.scopes:
                yield entry


def _safe_load(content: str) -> Dict[str, Any]:
    if yaml:
        return yaml.safe_load(content) or {}
    entries = []
    current: Dict[str, Any] | None = None
    defaults: Dict[str, Any] = {"tier": 1, "enabled": True}
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("defaults:"):
            continue
        if line.startswith("-"):
            if current:
                entries.append(current)
            parts = line.split(":", 1)
            current = {"id": parts[1].strip()} if len(parts) > 1 else {}
            continue
        if current is not None and ":" in line:
            key, val = line.split(":", 1)
            val = val.strip()
            if val.startswith("[") and val.endswith("]"):
                val = [v.strip() for v in val.strip("[]").split(",") if v.strip()]
            elif val.isdigit():
                val = int(val)
            elif val.lower() in {"true", "false"}:
                val = val.lower() == "true"
            current[key.strip()] = val
    if current:
        entries.append(current)
    return {"defaults": defaults, "entries": entries}
