"""Lightweight command-line interface for cugar-agent orchestration."""

from __future__ import annotations

import argparse
import json
import sys
import os
from pathlib import Path
from typing import List, Optional

from cuga.agents.controller import Controller
from cuga.agents.executor import Executor
from cuga.agents.planner import Planner, PlanningPreferences
from cuga.agents.registry import ToolRegistry
from cuga.plugins import list_plugins, load_plugins
from mcp.loader import load_registry, register_tools
from mcp.runner import MCPRunner


def _build_controller(plugin_paths: List[str]):
    registry = ToolRegistry()
    plugin_results = load_plugins(registry, plugin_paths)
    if os.getenv("CUGA_ENABLE_MCP", "false").lower() in {"1", "true", "yes", "on"}:
        mcp_registry = load_registry(os.getenv("CUGA_MCP_REGISTRY", "registry.yaml"))
        register_tools(
            registry,
            mcp_registry,
            MCPRunner(),
            profile=os.getenv("CUGA_MCP_PROFILE", "default"),
        )
    controller = Controller(planner=Planner(), executor=Executor(), registry=registry)
    return controller, plugin_results


def _resolve_profile(controller: Controller, profile: Optional[str]) -> str:
    profiles = sorted(controller.registry.profiles())
    if not profiles:
        raise SystemExit("No profiles available. Load plugins with --plugin to register tools.")
    if profile is None:
        return profiles[0]
    if profile not in profiles:
        raise SystemExit(f"Profile '{profile}' not found. Available: {', '.join(profiles)}")
    return profile


def handle_list(args: argparse.Namespace) -> int:
    controller, plugin_results = _build_controller(args.plugin or [])
    profiles = sorted(controller.registry.profiles())
    plugins = list_plugins(plugin_results)
    print(json.dumps({"profiles": profiles, "plugins": plugins}, indent=2))
    return 0


def handle_run(args: argparse.Namespace) -> int:
    controller, _ = _build_controller(args.plugin or [])
    resolved_profile = _resolve_profile(controller, args.profile)
    preferences = PlanningPreferences(optimization=args.optimize_for)
    result = controller.run(args.goal, resolved_profile, preferences=preferences)
    payload = {"profile": resolved_profile, "steps": result.steps, "output": result.output, "trace": result.trace}
    print(json.dumps(payload, indent=2))
    return 0


def handle_export(args: argparse.Namespace) -> int:
    controller, _ = _build_controller(args.plugin or [])
    resolved_profile = _resolve_profile(controller, args.profile)
    preferences = PlanningPreferences(optimization=args.optimize_for)
    result = controller.run(args.goal, resolved_profile, preferences=preferences)
    payload = {"profile": resolved_profile, "steps": result.steps, "output": result.output, "trace": result.trace}
    Path(args.output).write_text(json.dumps(payload, indent=2))
    print(f"Exported results to {args.output}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Interact with cugar-agent profiles and tools from the terminal.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List available agents and plugins.")
    list_parser.add_argument("--plugin", action="append", help="Path to a plugin module to load.")
    list_parser.set_defaults(func=handle_list)

    run_parser = subparsers.add_parser("run", help="Run a task and print the structured result.")
    run_parser.add_argument("goal", help="Goal or task for the agent to accomplish.")
    run_parser.add_argument("--profile", help="Target profile to execute under.")
    run_parser.add_argument("--plugin", action="append", help="Path to a plugin module to load.")
    run_parser.add_argument("--optimize-for", choices=["balanced", "cost", "latency"], default="balanced")
    run_parser.set_defaults(func=handle_run)

    export_parser = subparsers.add_parser("export", help="Run a task and export the structured result to disk.")
    export_parser.add_argument("goal", help="Goal or task for the agent to accomplish.")
    export_parser.add_argument("--output", required=True, help="Where to export the run results.")
    export_parser.add_argument("--profile", help="Target profile to execute under.")
    export_parser.add_argument("--plugin", action="append", help="Path to a plugin module to load.")
    export_parser.add_argument("--optimize-for", choices=["balanced", "cost", "latency"], default="balanced")
    export_parser.set_defaults(func=handle_export)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "func", None)
    if handler is None:
        parser.print_help()
        return 1
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
