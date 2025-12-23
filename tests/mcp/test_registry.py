import pathlib

import pytest

from cuga.mcp.config import MCPConfig, load_config
from cuga.mcp.interfaces import ToolSpec
from cuga.mcp.registry import MCPRegistry


def test_load_config_from_toml():
    cfg_path = pathlib.Path(__file__).with_name("sample_config.toml")
    cfg = load_config(str(cfg_path))
    assert "sample" in cfg.tools
    spec = cfg.tools["sample"]
    assert spec.alias == "sample"
    assert spec.command == "python"


def test_registry_get_and_list():
    cfg_path = pathlib.Path(__file__).with_name("sample_config.toml")
    cfg = MCPConfig.from_toml(str(cfg_path))
    registry = MCPRegistry(cfg)
    spec = registry.get("sample", version="1.0.0")
    assert spec.transport == "stdio"
    tools = registry.list()
    assert any(t.alias == "sample" for t in tools)
    with pytest.raises(KeyError):
        registry.get("missing")


def test_registry_version_mismatch_raises():
    cfg_path = pathlib.Path(__file__).with_name("sample_config.toml")
    cfg = MCPConfig.from_toml(str(cfg_path))
    registry = MCPRegistry(cfg)
    with pytest.raises(ValueError):
        registry.get("sample", version="2.0.0")


def test_registry_reload_and_discovery(monkeypatch):
    cfg_a = MCPConfig(tools={"alpha": ToolSpec(alias="alpha", name="alpha")})
    registry = MCPRegistry(cfg_a)
    cfg_b = MCPConfig(tools={"beta": ToolSpec(alias="beta", name="beta")})
    registry.reload(cfg_b)
    assert registry.get("beta").alias == "beta"
    with pytest.raises(KeyError):
        registry.get("alpha")

    class DummyEntry:
        name = "gamma"

        def load(self):
            return lambda: ToolSpec(alias="gamma", name="gamma")

    class DummyEntries(list):
        def select(self, group=None):
            if group == "cuga_mcp_servers":
                return self
            return []

    # Modern API
    monkeypatch.setattr("importlib.metadata.entry_points", lambda: DummyEntries([DummyEntry()]))
    registry.discover_entrypoints()
    assert registry.get("gamma").alias == "gamma"

    # Legacy mapping API
    registry.reload(cfg_b)
    monkeypatch.setattr("importlib.metadata.entry_points", lambda: {"cuga_mcp_servers": [DummyEntry()]})
    registry.discover_entrypoints()
    assert registry.get("gamma").alias == "gamma"

