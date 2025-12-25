from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Sequence

import yaml

REGISTRY_PATH = Path("docs/mcp/registry.yaml")
OUTPUT_PATH = Path("docs/mcp/tiers.md")
ENV_PATTERN = re.compile(r"\$\{([^}:]+)")


def _titleize(tool_id: str) -> str:
    parts = re.split(r"[._\-/]+", tool_id)
    return " ".join(p.capitalize() for p in parts if p)


def _merge_entry(defaults: Dict, entry: Dict) -> Dict:
    merged = {**defaults, **entry}
    merged["env"] = {**defaults.get("env", {}), **entry.get("env", {})}
    merged["mounts"] = entry.get("mounts", defaults.get("mounts", []))
    merged["scopes"] = entry.get("scopes", defaults.get("scopes", []))
    return merged


def _auth_env(env: Dict) -> str:
    keys: List[str] = []
    for val in env.values():
        if isinstance(val, str):
            matches = ENV_PATTERN.findall(val)
            if matches:
                keys.extend(matches)
            else:
                keys.append(val.split(":", 1)[0] if ":" in val else val)
    deduped = sorted(dict.fromkeys(k for k in keys if k))
    return ", ".join(deduped) if deduped else "none"


def _fs_scope(mounts: Sequence[str]) -> str:
    return "; ".join(mounts) if mounts else "none"


def _network_flag(protocol: str) -> str:
    return "on" if protocol else "off"


def _observability(scopes: Sequence[str]) -> str:
    return "TraceSink/Export" if "observability" in scopes else "TraceSink"


def _status(enabled: bool) -> str:
    return "on" if enabled else "off"


def _rows(data: Dict) -> List[Dict]:
    defaults = data.get("defaults", {})
    entries = [_merge_entry(defaults, e) for e in data.get("entries", [])]
    return sorted(entries, key=lambda e: (int(e.get("tier", 0)), _titleize(e["id"])))


def _render_table(rows: List[Dict]) -> str:
    header = [
        "| tool | tier | registry id | auth env vars | sandbox profile | fs scope | network | observability taps | status |",
        "|------|------|-------------|---------------|-----------------|---------|---------|--------------------|--------|",
    ]
    lines: List[str] = header.copy()
    for entry in rows:
        tool_name = entry.get("name") or _titleize(entry["id"])
        lines.append(
            "| {tool} | {tier} | {rid} | {auth} | {sandbox} | {fs} | {net} | {obs} | {status} |".format(
                tool=tool_name,
                tier=entry.get("tier", ""),
                rid=entry["id"],
                auth=_auth_env(entry.get("env", {})),
                sandbox=entry.get("sandbox", ""),
                fs=_fs_scope(entry.get("mounts", [])),
                net=_network_flag(entry.get("protocol", "")),
                obs=_observability(entry.get("scopes", [])),
                status=_status(entry.get("enabled", False)),
            )
        )
    lines.append("")
    return "\n".join(lines)


def generate() -> str:
    registry = yaml.safe_load(REGISTRY_PATH.read_text())
    rows = _rows(registry)
    preface = [
        "Tier 1: foundational defaults for orchestration, execution, filesystem, web/search, and VCS. Registry-driven, default enabled.",
        "Tier 2 + Unrated: optional finance/CMS/social/DB/vector/observability, default disabled. Unrated = community/experimental only.",
        "",
        "Integration matrix (source of truth: docs/mcp/registry.yaml; sandboxes in docs/compute/sandboxes.md; observability in docs/observability/config.md)",
    ]
    return "\n".join(preface + [_render_table(rows)])


def main() -> None:
    OUTPUT_PATH.write_text(generate())


if __name__ == "__main__":
    main()
