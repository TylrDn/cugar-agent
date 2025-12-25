import pytest

from cuga.mcp_servers.moon_agents import server


def test_moon_agents_list(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("CUGA_PROFILE_SANDBOX", str(tmp_path))
    resp = server._handle({"method": "run", "params": {"action": "list_patterns"}})
    assert resp["ok"] is True
    assert len(resp["result"]["patterns"]) >= 1


def test_moon_agents_invalid(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("CUGA_PROFILE_SANDBOX", str(tmp_path))
    with pytest.raises(server.RequestError):
        server._handle({"method": "run", "params": {"action": "generate_plan", "params": {}}})
