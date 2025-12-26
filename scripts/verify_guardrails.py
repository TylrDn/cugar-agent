from __future__ import annotations

import os
from pathlib import Path

from cuga.sandbox.isolation import ALLOWED_ENV_PREFIXES, filter_env, validate_tool_path


def verify_env_allowlist(env: dict) -> bool:
    return set(filter_env(env).keys()) == {k for k in env if k.startswith(ALLOWED_ENV_PREFIXES)}


def verify_import(path: str) -> bool:
    try:
        validate_tool_path(path)
        return True
    except ValueError:
        return False


def main() -> int:
    sample_env = {"AGENT_BUDGET_CEILING": "100", "UNSAFE": "1"}
    assert verify_env_allowlist(sample_env)
    assert verify_import("cuga.modular.tools.echo")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
