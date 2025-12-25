from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, Iterable

MAX_TWEET_LIMIT = 100


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


def _load_snscrape():
    try:
        from snscrape.modules import twitter  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise RequestError("snscrape is not available", type_="missing_dependency", details={"error": str(exc)}) from exc
    return twitter


def _serialize_tweet(tweet: Any) -> Dict[str, Any]:
    user = getattr(tweet, "user", None)
    username = getattr(user, "username", None) if user else None
    date = getattr(tweet, "date", None)
    date_iso = None
    if hasattr(date, "isoformat"):
        try:
            date_iso = date.isoformat()
        except Exception:  # noqa: BLE001
            date_iso = None
    return {
        "id": getattr(tweet, "id", None),
        "date": date_iso,
        "content": getattr(tweet, "content", None),
        "username": username,
        "url": getattr(tweet, "url", None),
    }


def _scrape(params: Dict[str, Any]) -> Dict[str, Any]:
    query = params.get("query")
    if not isinstance(query, str) or not query.strip():
        raise RequestError("'query' is required", details={"field": "query"})
    sandbox = _get_sandbox()
    limit = params.get("limit", 10)
    try:
        limit_int = int(limit)
    except Exception as exc:  # noqa: BLE001
        raise RequestError("'limit' must be an integer", details={"field": "limit"}) from exc
    if limit_int < 1:
        raise RequestError("'limit' must be positive", details={"field": "limit"})
    limit_int = min(limit_int, MAX_TWEET_LIMIT)

    _ = sandbox  # ensure sandbox binding for telemetry; no filesystem writes needed
    twitter = _load_snscrape()
    mode = params.get("mode")
    scraper = twitter.TwitterSearchScraper(query)
    tweets: list[Dict[str, Any]] = []
    for idx, tweet in enumerate(scraper.get_items()):
        if idx >= limit_int:
            break
        tweets.append(_serialize_tweet(tweet))
    return {"tweets": tweets, "mode": mode or "standard"}


def _handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    method = payload.get("method")
    params = payload.get("params", {}) if isinstance(payload.get("params", {}), dict) else {}
    if method == "health":
        return {"ok": True, "result": {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}}
    if method != "scrape":
        raise RequestError("Unsupported method", details={"method": method})
    result = _scrape(params)
    return {"ok": True, "result": result, "meta": {"tool": "scrape_tweets"}}


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
