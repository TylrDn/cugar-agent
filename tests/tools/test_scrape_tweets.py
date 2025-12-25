from datetime import datetime
import types
import sys

import pytest

from cuga.mcp_servers.scrape_tweets import server


class _User:
    def __init__(self, username: str) -> None:
        self.username = username


class _Tweet:
    def __init__(self, id_: int, content: str) -> None:
        self.id = id_
        self.content = content
        self.date = datetime(2024, 1, 1)
        self.user = _User("tester")
        self.url = f"https://example.com/{id_}"


def _install_fake_snscrape(monkeypatch: pytest.MonkeyPatch, *, tweet_count: int = 2) -> None:
    def _scraper(_: str):
        class Wrapper:
            def get_items(self):
                return [_Tweet(idx, f"tweet-{idx}") for idx in range(1, tweet_count + 1)]

        return Wrapper()

    fake_mod = types.SimpleNamespace(TwitterSearchScraper=_scraper)
    monkeypatch.setitem(sys.modules, "snscrape.modules.twitter", fake_mod)


def test_scrape_success(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("CUGA_PROFILE_SANDBOX", str(tmp_path))
    _install_fake_snscrape(monkeypatch)
    response = server._handle({"method": "scrape", "params": {"query": "openai", "limit": 1}})
    assert response["ok"] is True
    tweets = response["result"]["tweets"]
    assert len(tweets) == 1
    assert tweets[0]["username"] == "tester"


def test_scrape_invalid_query(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("CUGA_PROFILE_SANDBOX", str(tmp_path))
    with pytest.raises(server.RequestError) as excinfo:
        server._handle({"method": "scrape", "params": {"query": ""}})
    assert excinfo.value.type == "bad_request"


def test_scrape_invalid_limit_non_int(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("CUGA_PROFILE_SANDBOX", str(tmp_path))
    with pytest.raises(server.RequestError) as excinfo:
        server._handle({"method": "scrape", "params": {"query": "openai", "limit": "abc"}})
    assert excinfo.value.details["field"] == "limit"


def test_scrape_invalid_limit_non_positive(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("CUGA_PROFILE_SANDBOX", str(tmp_path))
    with pytest.raises(server.RequestError) as excinfo:
        server._handle({"method": "scrape", "params": {"query": "openai", "limit": 0}})
    assert excinfo.value.details["field"] == "limit"


def test_scrape_limit_capped(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("CUGA_PROFILE_SANDBOX", str(tmp_path))
    _install_fake_snscrape(monkeypatch, tweet_count=server.MAX_TWEET_LIMIT + 10)
    response = server._handle({"method": "scrape", "params": {"query": "openai", "limit": server.MAX_TWEET_LIMIT + 50}})
    assert len(response["result"]["tweets"]) == server.MAX_TWEET_LIMIT


def test_scrape_missing_sandbox(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("CUGA_PROFILE_SANDBOX", raising=False)
    with pytest.raises(server.RequestError) as excinfo:
        server._handle({"method": "scrape", "params": {"query": "openai"}})
    assert excinfo.value.type == "missing_env"


def test_scrape_missing_dependency(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("CUGA_PROFILE_SANDBOX", str(tmp_path))
    monkeypatch.setitem(sys.modules, "snscrape.modules.twitter", None)
    monkeypatch.delitem(sys.modules, "snscrape.modules.twitter", raising=False)
    with pytest.raises(server.RequestError) as excinfo:
        server._handle({"method": "scrape", "params": {"query": "openai"}})
    assert excinfo.value.type == "missing_dependency"


def test_scrape_health(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("CUGA_PROFILE_SANDBOX", str(tmp_path))
    response = server._handle({"method": "health"})
    assert response["ok"] is True
    assert response["result"]["status"] == "healthy"


def test_scrape_unknown_method(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("CUGA_PROFILE_SANDBOX", str(tmp_path))
    with pytest.raises(server.RequestError) as excinfo:
        server._handle({"method": "unknown"})
    assert excinfo.value.details["method"] == "unknown"
