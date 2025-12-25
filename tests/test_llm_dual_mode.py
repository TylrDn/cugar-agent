import json
from pathlib import Path

import httpx
import pytest
import respx

from cuga.llm.budget import BudgetConfig, BudgetExceeded, BudgetManager
from cuga.llm.factory import get_llm_client
from cuga.llm.openai_like import OpenAILikeClient
from cuga.llm.types import ChatMessage, Usage
from cuga import config as cuga_config


def write_settings(tmp_path: Path, content: str) -> Path:
    settings = tmp_path / "settings.toml"
    settings.write_text(content, encoding="utf-8")
    return settings


@pytest.fixture(autouse=True)
def patch_settings(monkeypatch, tmp_path):
    settings = write_settings(
        tmp_path,
        """
[llm]
provider="openai"
model="gpt-4o-mini"
base_url="http://localhost:9999"
api_key="${OPENAI_API_KEY}"
timeout_s=1
max_retries=0

[llm.fallback]
model="gpt-4o-mini"
api_key="fallback"
        """,
    )
    monkeypatch.setattr(cuga_config, "SETTINGS_TOML_PATH", str(settings))
    return settings


def test_env_expansion(monkeypatch, patch_settings):
    monkeypatch.setenv("OPENAI_API_KEY", "token-123")
    llm = cuga_config.load_llm_settings()
    assert llm.api_key == "token-123"


def test_budget_block(tmp_path):
    manager = BudgetManager(BudgetConfig(run_budget_usd=0.01, enforce="block"), ledger_path=tmp_path / "ledger.json")
    with pytest.raises(BudgetExceeded):
        manager.record(usage=Usage(prompt_tokens=1000), model="gpt-4o-mini", is_local=False)


@respx.mock
def test_factory_local(monkeypatch):
    respx.post("http://localhost:9999/v1/chat/completions").mock(return_value=httpx.Response(200, json={"choices": [{"message": {"content": "hi"}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1}, "model": "local"}))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = get_llm_client(env={})
    response = client.chat([ChatMessage(role="user", content="ping")])
    assert response.content == "hi"


@respx.mock
def test_hybrid_timeout(monkeypatch):
    respx.post("http://localhost:9999/v1/chat/completions").mock(side_effect=httpx.TimeoutException("boom"))
    respx.post("https://api.openai.com/v1/chat/completions").mock(return_value=httpx.Response(200, json={"choices": [{"message": {"content": "fallback"}}], "usage": {}, "model": "gpt"}))
    monkeypatch.setenv("OPENAI_API_KEY", "fallback")
    client = get_llm_client(env={})
    assert client.chat([ChatMessage(role="user", content="ping")]).content == "fallback"


def test_openai_like_retry(monkeypatch):
    call_count = {"n": 0}

    def handler(request):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise httpx.TimeoutException("t")
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1}, "model": "m"})

    with respx.mock(base_url="http://localhost:9999") as router:
        router.post("/v1/chat/completions").mock(side_effect=handler)
        client = OpenAILikeClient(model="m", base_url="http://localhost:9999", max_retries=1)
        assert client.chat([ChatMessage(role="user", content="hi")]).content == "ok"
        assert call_count["n"] == 2
