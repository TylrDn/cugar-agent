#!/usr/bin/env python3
"""Merge MCP registry fragments defined by a profile."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import tomllib
import yaml


def load_profile(profile_name: str, profiles_dir: Path) -> Tuple[dict, Path]:
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

    langflow_prod_projects = profile.get("langflow_prod_projects", {})
    if langflow_prod_projects is None:
        langflow_prod_projects = {}
    if not isinstance(langflow_prod_projects, dict):
        raise ValueError("'langflow_prod_projects' must be a mapping of project names to env vars")

    return {
        "fragments": fragments,
        "output": output,
        "langflow_prod_projects": langflow_prod_projects,
    }, profile_path


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


def create_langflow_prod_config(project_id_env_var: str) -> Dict[str, Any]:
    return {
        "transport": "stdio",
        "command": "uvx",
        "args": [
            "mcp-proxy",
            "--headers",
            "x-api-key",
            "${LF_API_KEY:?LF_API_KEY is required for prod services}",
            f"${{LF_SERVER:-http://localhost:7860}}/api/v1/mcp/project/{project_id_env_var}/streamable",
        ],
        "description": f"Langflow Project ({project_id_env_var}, PROD via proxy, STDIO)",
    }


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        try:
            return yaml.safe_load(f) or {}
        except yaml.YAMLError as err:
            raise ValueError(f"Invalid YAML in {path}: {err}") from err


def merge_fragments(
    fragment_paths: List[Path],
    *,
    langflow_prod_projects: Dict[str, str] | None = None,
) -> dict:
    merged_mcp_servers: Dict[str, Any] = {}
    merged_services: Dict[str, Any] = {}
    mcp_server_sources: Dict[str, Path] = {}
    service_sources: Dict[str, Path] = {}

    for path in fragment_paths:
        if not path.exists():
            raise FileNotFoundError(f"Fragment not found: {path}")
        content = _load_yaml(path)

        mcp_servers = _validate_mcp_servers(content.get("mcpServers"), path)
        services = _validate_services(content.get("services"), path)

        for name, details in mcp_servers.items():
            if name in merged_mcp_servers:
                raise ValueError(
                    f"Duplicate mcpServers entry '{name}' found in {path} and {mcp_server_sources[name]}"
                )
            merged_mcp_servers[name] = details
            mcp_server_sources[name] = path

        for service in services:
            name, details = next(iter(service.items()))
            if name in merged_services:
                raise ValueError(
                    f"Duplicate service entry '{name}' found in {path} and {service_sources[name]}"
                )
            merged_services[name] = details
            service_sources[name] = path

    langflow_prod_projects = langflow_prod_projects or {}
    for project_name, project_id_env_var in langflow_prod_projects.items():
        server_key = f"langflow_{project_name}"
        if server_key in merged_mcp_servers:
            print(
                f"[deprecation] Legacy Langflow fragment already defines '{server_key}' (source: {mcp_server_sources[server_key]}). "
                "Prefer removing the fragment and using 'langflow_prod_projects' in the profile.",
                file=sys.stderr,
            )
            continue
        merged_mcp_servers[server_key] = create_langflow_prod_config(project_id_env_var)

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
    profile, profile_path = load_profile(args.profile, args.profiles_dir)

    fragment_paths = [Path(path) if Path(path).is_absolute() else profile_path.parent / path for path in profile["fragments"]]
    merged = merge_fragments(fragment_paths, langflow_prod_projects=profile.get("langflow_prod_projects"))

    if not isinstance(merged.get("mcpServers"), dict) or not isinstance(merged.get("services"), list):
        raise ValueError("Merged output must include 'mcpServers' (dict) and 'services' (list)")

    output_path = Path(profile["output"])
    emit_output(merged, output_path, args.dry_run)


if __name__ == "__main__":
    main()
