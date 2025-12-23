#!/usr/bin/env python3
"""Merge MCP registry fragments defined by a profile."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List

import tomllib
import yaml


def load_profile(profile_name: str, profiles_dir: Path) -> dict:
    profile_path = profiles_dir / f"{profile_name}.toml"
    if not profile_path.exists():
        raise FileNotFoundError(f"Profile file not found: {profile_path}")

    with profile_path.open("rb") as f:
        profile_data = tomllib.load(f)

    profiles = profile_data.get("profiles")
    if not isinstance(profiles, dict) or profile_name not in profiles:
        raise KeyError(f"Profile '{profile_name}' not found in {profile_path}")

    profile = profiles[profile_name]
    fragments = profile.get("fragments")
    if not isinstance(fragments, list) or not fragments:
        raise ValueError(f"Profile '{profile_name}' must define a non-empty 'fragments' list")

    output = profile.get("output")
    if not isinstance(output, str) or not output:
        raise ValueError(f"Profile '{profile_name}' must define an 'output' path")

    return {"fragments": fragments, "output": output}


def _validate_mcp_servers(mcp_servers: Any, source: Path) -> Dict[str, Any]:
    if mcp_servers is None:
        return {}
    if not isinstance(mcp_servers, dict):
        raise TypeError(f"mcpServers must be a mapping in {source}")
    return mcp_servers


def _validate_services(services: Any, source: Path) -> List[dict]:
    if services is None:
        return []
    if not isinstance(services, list):
        raise TypeError(f"services must be a list in {source}")
    validated: List[dict] = []
    for entry in services:
        if not isinstance(entry, dict) or len(entry) != 1:
            raise ValueError(f"Each service entry must be a single-key mapping in {source}")
        validated.append(entry)
    return validated


def merge_fragments(fragment_paths: List[Path]) -> dict:
    merged_mcp_servers: Dict[str, Any] = {}
    merged_services: Dict[str, Any] = {}

    for path in fragment_paths:
        if not path.exists():
            raise FileNotFoundError(f"Fragment not found: {path}")
        with path.open("r", encoding="utf-8") as f:
            content = yaml.safe_load(f) or {}

        mcp_servers = _validate_mcp_servers(content.get("mcpServers"), path)
        services = _validate_services(content.get("services"), path)

        merged_mcp_servers.update(mcp_servers)

        for service in services:
            name, details = next(iter(service.items()))
            merged_services[name] = details

    services_list = [{name: details} for name, details in merged_services.items()]
    return {"mcpServers": merged_mcp_servers, "services": services_list}


def emit_output(merged: dict, destination: Path, dry_run: bool) -> None:
    yaml_output = yaml.safe_dump(merged, sort_keys=False, allow_unicode=True)
    if dry_run:
        sys.stdout.write(yaml_output)
        return

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(yaml_output, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge MCP registry fragments using a profile")
    parser.add_argument("--profile", required=True, help="Profile name defined under configurations/profiles")
    parser.add_argument("--dry-run", action="store_true", help="Print merged YAML instead of writing to file")
    parser.add_argument(
        "--profiles-dir",
        type=Path,
        default=Path("./configurations/profiles"),
        help="Directory containing profile TOML files",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    profile = load_profile(args.profile, args.profiles_dir)

    fragment_paths = [Path(path) for path in profile["fragments"]]
    merged = merge_fragments(fragment_paths)

    if not isinstance(merged.get("mcpServers"), dict) or not isinstance(merged.get("services"), list):
        raise ValueError("Merged output must include 'mcpServers' (dict) and 'services' (list)")

    output_path = Path(profile["output"])
    emit_output(merged, output_path, args.dry_run)


if __name__ == "__main__":
    main()
