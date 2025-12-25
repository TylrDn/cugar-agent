from __future__ import annotations

from pathlib import Path

import pytest

from cuga.mcp_v2.registry.errors import RegistryMergeError, RegistryValidationError
from cuga.mcp_v2.registry.loader import _env_enabled, _parse_tool, load_mcp_registry_snapshot


@pytest.fixture()
def tmp_registry(tmp_path: Path) -> Path:
    base = tmp_path / "registry.yaml"
    fragment = tmp_path / "fragments" / "extra.yaml"
    fragment.parent.mkdir(parents=True)
    base.write_text(
        """
defaults:
  - _self_
  - fragments/extra
servers:
  base:
    url: ${oc.env:BASE_URL, "http://base.test"}
    enabled: true
    enabled_env: BASE_FLAG
    tools:
      - name: base_tool
        operation_id: baseOp
""".strip()
    )
    fragment.write_text(
        """
servers:
  fragment:
    url: ${oc.env:FRAG_URL, "http://frag.test"}
    enabled: true
    tools:
      - name: frag_tool
        operation_id: fragOp
""".strip()
    )
    return base


def test_hydra_fragment_merge_and_env(monkeypatch, tmp_registry: Path):
    monkeypatch.setenv("BASE_FLAG", "1")
    monkeypatch.setenv("BASE_URL", "http://override.base")
    monkeypatch.setenv("FRAG_URL", "http://fragment.override")

    snapshot = load_mcp_registry_snapshot(tmp_registry)

    urls = {server.name: server.url for server in snapshot.servers}
    assert urls == {
        "base": "http://override.base",
        "fragment": "http://fragment.override",
    }
    assert snapshot.sources and tmp_registry in snapshot.sources


def test_duplicates_only_for_enabled(monkeypatch, tmp_path: Path):
    base = tmp_path / "registry.yaml"
    frag_one = tmp_path / "fragments" / "one.yaml"
    frag_two = tmp_path / "fragments" / "two.yaml"
    frag_one.parent.mkdir(parents=True)

    base.write_text(
        """
defaults:
  - _self_
  - fragments/one
  - fragments/two
servers:
  shadow:
    url: http://disabled
    enabled: false
""".strip()
    )
    frag_one.write_text(
        """
servers:
  shadow:
    url: http://enabled.one
    enabled: true
""".strip()
    )
    frag_two.write_text(
        """
servers:
  shadow:
    url: http://enabled.two
    enabled: true
""".strip()
    )

    with pytest.raises(RegistryMergeError):
        load_mcp_registry_snapshot(base)

    frag_two.write_text(
        """
servers:
  shadow:
    url: http://enabled.two
    enabled: false
""".strip()
    )

    snapshot = load_mcp_registry_snapshot(base)
    assert [server.url for server in snapshot.servers] == ["http://enabled.one"]


def test_tool_method_and_path_type_validation():
    with pytest.raises(RegistryValidationError):
        _parse_tool("bad", {"method": 123, "path": "/foo"}, {})
    with pytest.raises(RegistryValidationError):
        _parse_tool("bad", {"method": "get", "path": 5}, {})
    with pytest.raises(RegistryValidationError):
        _parse_tool("bad", {"operation_id": 9, "method": "get", "path": "/foo"}, {})


def test_env_enabled_semantics(monkeypatch):
    env = {"FLAG": "1"}
    assert _env_enabled({"enabled": True, "enabled_env": "FLAG"}, env)
    assert _env_enabled({"enabled": False, "enabled_env": "FLAG"}, env)
    # When the environment key is absent, fall back to the config-enabled flag
    assert _env_enabled({"enabled": True, "enabled_env": "MISSING"}, env)
    assert not _env_enabled({"enabled": False, "enabled_env": "MISSING"}, env)
    assert _env_enabled({"enabled": True}, env)


def test_roundtrip_with_repo_config(monkeypatch):
    repo_root = Path(__file__).resolve().parents[1]
    config_path = repo_root / "config" / "registry.yaml"
    monkeypatch.setenv("SAMPLE_ECHO_ENABLED", "1")
    snapshot = load_mcp_registry_snapshot(config_path)
    assert any(server.name == "sample_echo" for server in snapshot.servers)
