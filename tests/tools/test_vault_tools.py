import pytest

from cuga.mcp_servers.vault_tools import server


def test_vault_json_query(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("CUGA_PROFILE_SANDBOX", str(tmp_path))
    payload = {
        "method": "execute",
        "params": {
            "tool": "json_query",
            "params": {"data": {"items": [{"name": "alice"}]}, "expression": "items[0].name"},
        },
    }
    resp = server._handle(payload)
    assert resp["ok"] is True
    assert resp["result"]["result"] == "alice"


def test_vault_kv_isolated(tmp_path_factory):
    sandbox_a = tmp_path_factory.mktemp("sandbox_a")
    sandbox_b = tmp_path_factory.mktemp("sandbox_b")

    def _set_value(path, key, value):
        payload = {
            "method": "execute",
            "params": {"tool": "kv_store", "params": {"action": "set", "key": key, "value": value}},
        }
        return server._handle(payload)

    def _get_value(path, key):
        payload = {
            "method": "execute",
            "params": {"tool": "kv_store", "params": {"action": "get", "key": key}},
        }
        return server._handle(payload)

    # set in sandbox A
    import os

    os.environ["CUGA_PROFILE_SANDBOX"] = str(sandbox_a)
    _set_value(sandbox_a, "foo", "bar")

    # read from sandbox B should be isolated
    os.environ["CUGA_PROFILE_SANDBOX"] = str(sandbox_b)
    result_b = _get_value(sandbox_b, "foo")
    assert result_b["result"]["result"] is None
