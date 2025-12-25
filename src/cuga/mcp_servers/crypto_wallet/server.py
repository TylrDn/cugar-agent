from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime
from typing import Any, Dict, List

from cuga.mcp_servers._shared import RequestError, get_sandbox, run_main

# WARNING: This module is for testing/demonstration only and does not provide
# production-grade cryptography, key storage, or wallet security. Do not use
# real mnemonics or secrets generated here in any live environment.


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
        # Deterministic derivation for tests only; not secure.
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
    # HMAC is deterministic and for testing only; not a secure wallet signature.
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).hexdigest()


def _handle_operation(operation: str, params: Dict[str, Any]) -> Dict[str, Any]:
    _ = get_sandbox()
    if operation == "generate_mnemonic":
        word_count_raw = params.get("word_count", 12)
        try:
            word_count = int(word_count_raw)
        except Exception as exc:  # noqa: BLE001
            raise RequestError(
                "'word_count' must be an integer",
                type_="invalid_request",
                details={"field": "word_count"},
            ) from exc
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
    run_main(_handle)


if __name__ == "__main__":
    main()
