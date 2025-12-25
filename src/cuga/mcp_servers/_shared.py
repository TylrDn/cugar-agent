from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Callable, Dict


class RequestError(Exception):
    """Standardized error for MCP servers."""

    def __init__(self, message: str, *, type_: str = "bad_request", details: Dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.type = type_
        self.details = details or {}


def get_sandbox(*, as_path: bool = False) -> str | Path:
    sandbox = os.getenv("CUGA_PROFILE_SANDBOX")
    if not sandbox:
        raise RequestError("CUGA_PROFILE_SANDBOX is required for sandboxed execution", type_="missing_env")
    return Path(sandbox) if as_path else sandbox


def load_payload() -> Dict[str, Any]:
    if "--json" in sys.argv:
        try:
            idx = sys.argv.index("--json") + 1
            return json.loads(sys.argv[idx])
        except Exception as exc:  # noqa: BLE001
            raise RequestError("Invalid JSON payload", details={"error": str(exc)}) from exc
    raw = sys.stdin.read().strip() or "{}"
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise RequestError("Invalid JSON payload", details={"error": str(exc)}) from exc


def _write_stdout(message: Dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(message) + "\n")
    sys.stdout.flush()


def run_main(handler: Callable[[Dict[str, Any]], Dict[str, Any]]) -> None:
    try:
        payload = load_payload()
        response = handler(payload)
        _write_stdout(response)
    except RequestError as exc:
        error_body = {"ok": False, "error": {"type": exc.type, "message": str(exc), "details": exc.details}}
        _write_stdout(error_body)
        sys.stderr.write(str(exc) + "\n")
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001
        error_body = {"ok": False, "error": {"type": "unexpected", "message": str(exc)}}
        _write_stdout(error_body)
        sys.stderr.write(str(exc) + "\n")
        sys.exit(1)
