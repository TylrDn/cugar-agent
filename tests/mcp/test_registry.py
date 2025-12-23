import pathlib

import pytest

from cuga.mcp.config import MCPConfig, load_config
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

