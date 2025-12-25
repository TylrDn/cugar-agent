from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
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


WORD_LIST = [
    "circle",
    "agent",
    "vault",
    "crypto",
    "matrix",
    "signal",
    "bridge",
    "neon",
    "quantum",
    "ledger",
    "python",
    "secure",
    "future",
    "vector",
]


def _generate_mnemonic(count: int = 12, seed: int | None = None) -> str:
    if count not in (12, 24):
        raise RequestError("'word_count' must be 12 or 24", details={"field": "word_count"})
    if seed is not None:
        hash_seed = hashlib.sha256(str(seed).encode("utf-8")).digest()

        def _seq() -> int:
            nonlocal hash_seed
            hash_seed = hashlib.sha256(hash_seed).digest()
            return int.from_bytes(hash_seed, "big")

        def _choice(options: List[str]) -> str:
            return options[_seq() % len(options)]

        return " ".join(_choice(WORD_LIST) for _ in range(count))
    rng = secrets.SystemRandom()
    return " ".join(rng.choice(WORD_LIST) for _ in range(count))


def _validate_mnemonic(mnemonic: str) -> bool:
    words = mnemonic.strip().split()
    return len(words) in (12, 24) and all(word in WORD_LIST for word in words)


def _derive_address(mnemonic: str, derivation_path: str | None = None) -> str:
    if not _validate_mnemonic(mnemonic):
        raise RequestError("Invalid mnemonic", type_="invalid_mnemonic")
    path = derivation_path or "m/44'/60'/0'/0/0"
    digest = hashlib.sha256(f"{mnemonic}:{path}".encode("utf-8")).hexdigest()
    return "0x" + digest[:40]


def _sign_message(mnemonic: str, message: str) -> str:
    if not _validate_mnemonic(mnemonic):
        raise RequestError("Invalid mnemonic", type_="invalid_mnemonic")
    key = hashlib.sha256(mnemonic.encode("utf-8")).digest()
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).hexdigest()


def _handle_operation(operation: str, params: Dict[str, Any]) -> Dict[str, Any]:
    _ = _get_sandbox()
    if operation == "generate_mnemonic":
        word_count = int(params.get("word_count", 12)) if params.get("word_count") is not None else 12
        seed = params.get("seed")
        seed_int = int(seed) if isinstance(seed, (int, str)) and str(seed).isdigit() else None
        mnemonic = _generate_mnemonic(word_count, seed=seed_int)
        return {"data": {"mnemonic": mnemonic}}
    if operation == "validate_mnemonic":
        mnemonic = params.get("mnemonic", "")
        return {"data": {"valid": _validate_mnemonic(mnemonic)}}
    if operation == "derive_address":
        mnemonic = params.get("mnemonic", "")
        path = params.get("derivation_path")
        address = _derive_address(mnemonic, path)
        return {"data": {"address": address, "derivation_path": path or "m/44'/60'/0'/0/0"}}
    if operation == "sign_message":
        mnemonic = params.get("mnemonic", "")
        message = params.get("message")
        if not isinstance(message, str):
            raise RequestError("'message' is required", details={"field": "message"})
        signature = _sign_message(mnemonic, message)
        return {"data": {"signature": signature}}
    raise RequestError("Unsupported operation", details={"operation": operation})


def _handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    method = payload.get("method")
    params = payload.get("params", {}) if isinstance(payload.get("params", {}), dict) else {}
    if method == "health":
        return {"ok": True, "result": {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}}
    if method != "operate":
        raise RequestError("Unsupported method", details={"method": method})
    operation = params.get("operation")
    if not isinstance(operation, str):
        raise RequestError("'operation' must be provided", details={"field": "operation"})
    result = _handle_operation(operation, params.get("params", {}) if isinstance(params.get("params", {}), dict) else {})
    return {"ok": True, "result": result, "meta": {"tool": "crypto_wallet", "operation": operation}}


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
