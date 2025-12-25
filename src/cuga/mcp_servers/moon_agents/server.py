from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, List


class RequestError(Exception):
    def __init__(self, message: str, *, type_: str = "bad_request", details: Dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.type = type_
        self.details = details or {}


def _get_sandbox() -> str:
    sandbox = os.getenv("CUGA_PROFILE_SANDBOX")
    if not sandbox:
        raise RequestError("CUGA_PROFILE_SANDBOX is required for sandboxed execution", type_="missing_env")
    return sandbox


def _load_payload() -> Dict[str, Any]:
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


PATTERNS = [
    {"name": "research-assistant", "description": "Plans web and document research tasks."},
    {"name": "summarizer", "description": "Condenses long-form content into concise notes."},
    {"name": "planner", "description": "Generates structured plans for multi-step goals."},
]


def _list_patterns() -> Dict[str, Any]:
    _ = _get_sandbox()
    return {"patterns": PATTERNS}


def _generate_plan(params: Dict[str, Any]) -> Dict[str, Any]:
    sandbox = _get_sandbox()
    goal = params.get("goal")
    if not isinstance(goal, str) or not goal.strip():
        raise RequestError("'goal' is required", details={"field": "goal"})
    steps: List[Dict[str, Any]] = []
    steps.append({"step": 1, "action": "analyze_goal", "detail": goal})
    steps.append({"step": 2, "action": "select_tools", "detail": params.get("tools", [])})
    steps.append({"step": 3, "action": "deliver_plan", "detail": "Return structured plan"})
    return {"plan": {"goal": goal, "steps": steps, "sandbox": sandbox}}


def _handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    method = payload.get("method")
    params = payload.get("params", {}) if isinstance(payload.get("params", {}), dict) else {}
    if method == "health":
        return {"ok": True, "result": {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}}
    if method != "run":
        raise RequestError("Unsupported method", details={"method": method})
    action = params.get("action")
    if action == "list_patterns":
        result = _list_patterns()
    elif action == "generate_plan":
        result = _generate_plan(params.get("params", {}) if isinstance(params.get("params", {}), dict) else {})
    else:
        raise RequestError("Unsupported action", details={"action": action})
    return {"ok": True, "result": result, "meta": {"tool": "moon_agents", "action": action}}


def main() -> None:
    try:
        payload = _load_payload()
        response = _handle(payload)
        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()
    except RequestError as exc:
        error_body = {"ok": False, "error": {"type": exc.type, "message": str(exc), "details": exc.details}}
        sys.stdout.write(json.dumps(error_body) + "\n")
        sys.stdout.flush()
        sys.stderr.write(str(exc) + "\n")
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001
        error_body = {"ok": False, "error": {"type": "unexpected", "message": str(exc)}}
        sys.stdout.write(json.dumps(error_body) + "\n")
        sys.stdout.flush()
        sys.stderr.write(str(exc) + "\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
