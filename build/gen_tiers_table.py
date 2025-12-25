#!/usr/bin/env python3
import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = REPO_ROOT / "docs" / "mcp" / "registry.yaml"
TIERS_PATH = REPO_ROOT / "docs" / "mcp" / "tiers.md"

ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)(:[^}]*)?\}")

TIER_ORDER = ["1", "2", "unrated"]


def load_registry(path: Path):
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    tools = data.get("tools", []) if data else []
    return tools


def extract_auth_env(env_map):
    names = set()
    for val in (env_map or {}).values():
        if not isinstance(val, str):
            continue
        for match in ENV_PATTERN.findall(val):
            names.add(match[0])
    return sorted(names)


def format_mounts(mounts):
    if not mounts:
        return "-"
    return ", ".join(str(m) for m in mounts)


def tier_key(entry):
    tier = str(entry.get("tier", "unrated"))
    try:
        tier_index = TIER_ORDER.index(tier)
    except ValueError:
        tier_index = len(TIER_ORDER)
    name = entry.get("name") or str(entry.get("id", "")).replace("_", " ").title()
    return (tier_index, name.lower())


def render_table(entries):
    header = (
        "| tool | tier | registry id | auth env vars | sandbox profile | fs scope | network | observability taps | status |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
    )
    lines = []
    for entry in sorted(entries, key=tier_key):
        tool_name = entry.get("name") or str(entry.get("id", "")).replace("_", " ").title()
        tier_label = f"Tier {entry.get('tier', 'unrated')}"
        registry_id = entry.get("id", "-")
        auth_env = ", ".join(extract_auth_env(entry.get("env"))) or "-"
        sandbox = entry.get("sandbox", "-")
        fs_scope = format_mounts(entry.get("mounts"))
        network = entry.get("network", "-")
        observability = entry.get("observability", "-")
        status = "enabled" if entry.get("enabled") else "disabled"
        lines.append(
            f"| {tool_name} | {tier_label} | {registry_id} | {auth_env} | {sandbox} | {fs_scope} | {network} | {observability} | {status} |"
        )
    return header + "\n".join(lines) + "\n"


def build_content(entries):
    intro = (
        "# MCP Tiers\n\n"
        "Tier 1 integrations are foundational and default-on; Tier 2 integrations are optional and default disabled. Unrated entries cover community plugins and are never enabled by default.\n\n"
        "The integration matrix below is generated from `docs/mcp/registry.yaml` to avoid drift. See `../compute/sandboxes.md` for sandbox profiles and `../observability/config.md` for telemetry env keys.\n\n"
    )
    return intro + render_table(entries)


def main():
    entries = load_registry(REGISTRY_PATH)
    content = build_content(entries)
    TIERS_PATH.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
