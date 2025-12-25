from __future__ import annotations

from datetime import datetime
from itertools import islice
from typing import Any, Dict

from cuga.mcp_servers._shared import RequestError, get_sandbox, run_main

MAX_TWEET_LIMIT = 100


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
    _ = get_sandbox()
    limit = params.get("limit", 10)
    try:
        limit_int = int(limit)
    except Exception as exc:  # noqa: BLE001
        raise RequestError("'limit' must be an integer", details={"field": "limit"}) from exc
    if limit_int < 1:
        raise RequestError("'limit' must be positive", details={"field": "limit"})
    limit_int = min(limit_int, MAX_TWEET_LIMIT)

    twitter = _load_snscrape()
    mode = params.get("mode")
    scraper = twitter.TwitterSearchScraper(query)
    tweets = [_serialize_tweet(tweet) for tweet in islice(scraper.get_items(), limit_int)]
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
    run_main(_handle)


if __name__ == "__main__":
    main()
