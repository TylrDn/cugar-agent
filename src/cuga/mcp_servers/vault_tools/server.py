from __future__ import annotations

import json
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from cuga.mcp_servers._shared import RequestError, get_sandbox, run_main

try:
    import fcntl
except Exception:  # pragma: no cover - platform without fcntl
    fcntl = None  # type: ignore


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


@contextmanager
def _lock_path(path: Path):
    if fcntl is None:
        raise RequestError(
            "File locking is not supported on this platform",
            type_="unsupported_platform",
            details={"path": str(path)},
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield handle
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _read_store(handle) -> Dict[str, Any]:
    handle.seek(0)
    content = handle.read().strip()
    if not content:
        return {}
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise RequestError(
            "KV store is corrupt",
            type_="corrupt_store",
            details={"path": handle.name, "error": str(exc)},
        ) from exc


def _write_store(handle, data: Dict[str, Any]) -> None:
    path = Path(handle.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=path.name + ".tmp.",
        delete=False,
    ) as tmp:
        json.dump(data, tmp)
        tmp.flush()
        os.fsync(tmp.fileno())
    os.replace(tmp.name, path)
    dir_fd = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def _kv_store(params: Dict[str, Any], sandbox: Path) -> Dict[str, Any]:
    action = params.get("action")
    if action not in {"get", "set"}:
        raise RequestError("Invalid kv_store action", details={"action": action})
    key = params.get("key")
    if not isinstance(key, str) or not key:
        raise RequestError("'key' is required", details={"field": "key"})
    store_path = _kv_path(sandbox)

    with _lock_path(store_path) as handle:
        store = _read_store(handle)
        if action == "get":
            return {"result": store.get(key)}
        value = params.get("value")
        store[key] = value
        _write_store(handle, store)
        return {"result": value}


def _execute_tool(tool: str, params: Dict[str, Any]) -> Dict[str, Any]:
    sandbox = get_sandbox(as_path=True)
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
    run_main(_handle)


if __name__ == "__main__":
    main()
