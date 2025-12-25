from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


class RequestError(Exception):
    def __init__(self, message: str, *, type_: str = "bad_request", details: Dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.type = type_
        self.details = details or {}


def _get_sandbox() -> Path:
    sandbox = os.getenv("CUGA_PROFILE_SANDBOX")
    if not sandbox:
        raise RequestError("CUGA_PROFILE_SANDBOX is required for sandboxed execution", type_="missing_env")
    return Path(sandbox)


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


def _json_query(data: Any, expression: str) -> Any:
    # minimal dotted path accessor with list index support
    parts: List[str] = []
    buf = ""
    idx = 0
    while idx < len(expression):
        ch = expression[idx]
        if ch == ".":
            if buf:
                parts.append(buf)
                buf = ""
        elif ch == "[":
            if buf:
                parts.append(buf)
                buf = ""
            end = expression.find("]", idx)
            if end == -1:
                raise RequestError("Malformed query", details={"expression": expression})
            parts.append(expression[idx:end + 1])
            idx = end
        else:
            buf += ch
        idx += 1
    if buf:
        parts.append(buf)

    current: Any = data
    for part in parts:
        if part.startswith("[") and part.endswith("]"):
            try:
                index = int(part[1:-1])
            except ValueError as exc:  # noqa: BLE001
                raise RequestError("Invalid list index", details={"part": part}) from exc
            if not isinstance(current, list):
                raise RequestError("Expected list for index", details={"part": part})
            if index >= len(current) or index < -len(current):
                raise RequestError("Index out of range", details={"index": index})
            current = current[index]
        else:
            if not isinstance(current, dict) or part not in current:
                raise RequestError("Missing key in path", details={"part": part})
            current = current[part]
    return current


def _kv_path(base: Path) -> Path:
    kv_dir = base / "vault_tools"
    kv_dir.mkdir(parents=True, exist_ok=True)
    return kv_dir / "kv_store.json"


def _kv_store(params: Dict[str, Any], sandbox: Path) -> Dict[str, Any]:
    action = params.get("action")
    if action not in {"get", "set"}:
        raise RequestError("Invalid kv_store action", details={"action": action})
    key = params.get("key")
    if not isinstance(key, str) or not key:
        raise RequestError("'key' is required", details={"field": "key"})
    store_path = _kv_path(sandbox)
    store: Dict[str, Any] = {}
    if store_path.exists():
        try:
            store = json.loads(store_path.read_text())
        except Exception:  # noqa: BLE001
            store = {}
    if action == "get":
        return {"result": store.get(key)}
    value = params.get("value")
    store[key] = value
    store_path.write_text(json.dumps(store))
    return {"result": value}


def _execute_tool(tool: str, params: Dict[str, Any]) -> Dict[str, Any]:
    sandbox = _get_sandbox()
    sandbox.mkdir(parents=True, exist_ok=True)
    if tool == "time_now":
        return {"result": datetime.now(timezone.utc).isoformat()}
    if tool == "json_query":
        data = params.get("data")
        expr = params.get("expression")
        if expr is None or not isinstance(expr, str):
            raise RequestError("'expression' is required", details={"field": "expression"})
        return {"result": _json_query(data, expr)}
    if tool == "kv_store":
        return _kv_store(params, sandbox)
    raise RequestError("Unsupported tool", details={"tool": tool})


def _handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    method = payload.get("method")
    params = payload.get("params", {}) if isinstance(payload.get("params", {}), dict) else {}
    if method == "health":
        return {"ok": True, "result": {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}}
    if method != "execute":
        raise RequestError("Unsupported method", details={"method": method})
    tool = params.get("tool")
    if not isinstance(tool, str):
        raise RequestError("'tool' must be provided", details={"field": "tool"})
    result = _execute_tool(tool, params.get("params", {}) if isinstance(params.get("params", {}), dict) else {})
    return {"ok": True, "result": result, "meta": {"tool": tool}}


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
