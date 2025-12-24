import sys
import types
from datetime import datetime

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


def _install_fake_snscrape(monkeypatch: pytest.MonkeyPatch) -> None:
    def _scraper(_: str):
        class Wrapper:
            def get_items(self):
                return [_Tweet(1, "hello"), _Tweet(2, "world")]

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
    with pytest.raises(server.RequestError):
        server._handle({"method": "scrape", "params": {"query": ""}})
