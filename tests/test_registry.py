"""Tests for MCP registry loader functionality."""

import tempfile
from pathlib import Path

import pytest

from src.cuga.tools.mcp_registry import (
    MCPRegistryLoader,
    MCPToolManifest,
    UnregisteredToolError,
    load_mcp_registry,
)


@pytest.fixture
def sample_registry_yaml():
    """Create a sample registry YAML for testing."""
    return """
version: v1
defaults:
  tier: 1
  enabled: true
  protocol: mcp
  sandbox: py-slim
  scopes: []
  env:
    AGENT_BUDGET_CEILING: "100"
  mounts: []
  budget_policy: warn

entries:
  - id: mcp.github
    ref: docker://github
    scopes: [vcs]
    env:
      GITHUB_TOKEN: '${GITHUB_TOKEN:?}'
    mounts: []
  
  - id: mcp.fs
    ref: docker://filesystem
    scopes: [fs]
    mounts: [/workspace:ro, /workspace/output:rw]
  
  - id: mcp.crypto
    tier: 2
    enabled: false
    sandbox: py-full
    ref: docker://crypto
    scopes: [finance]
    env:
      CRYPTO_API_KEY: '${CRYPTO_API_KEY:-}'
    mounts: []
  
  - id: mcp.browser
    sandbox: node-full
    ref: docker://browser
    scopes: [web]
    mounts: []
"""


@pytest.fixture
def registry_file(sample_registry_yaml, tmp_path):
    """Create a temporary registry file."""
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(sample_registry_yaml)
    return registry_path


def test_registry_loading(registry_file):
    """Test that the registry loads correctly from YAML."""
    loader = MCPRegistryLoader(registry_path=registry_file)
    loader.load()
    
    # Should load enabled tools only
    assert loader.has_tool("mcp.github")
    assert loader.has_tool("mcp.fs")
    assert loader.has_tool("mcp.browser")
    assert not loader.has_tool("mcp.crypto")  # disabled


def test_deny_by_default(registry_file):
    """Test that unregistered tools raise an error."""
    loader = MCPRegistryLoader(registry_path=registry_file)
    loader.load()
    
    with pytest.raises(UnregisteredToolError) as exc_info:
        loader.get_manifest("mcp.nonexistent")
    
    assert "not registered" in str(exc_info.value)
    assert "mcp.nonexistent" in str(exc_info.value)


def test_manifest_resolution(registry_file):
    """Test manifest resolution with all fields."""
    loader = MCPRegistryLoader(registry_path=registry_file)
    loader.load()
    
    manifest = loader.get_manifest("mcp.github")
    assert isinstance(manifest, MCPToolManifest)
    assert manifest.id == "mcp.github"
    assert manifest.tier == 1
    assert manifest.enabled is True
    assert manifest.protocol == "mcp"
    assert manifest.ref == "docker://github"
    assert manifest.sandbox == "py-slim"
    assert manifest.scopes == ["vcs"]
    assert "GITHUB_TOKEN" in manifest.env
    assert manifest.budget_policy == "warn"


def test_stable_sorting(registry_file):
    """Test that tools are returned in stable sorted order."""
    loader = MCPRegistryLoader(registry_path=registry_file)
    loader.load()
    
    manifests = loader.list_manifests()
    ids = [m.id for m in manifests]
    
    # Should be alphabetically sorted
    assert ids == sorted(ids)
    
    # Should be deterministic across multiple calls
    manifests2 = loader.list_manifests()
    ids2 = [m.id for m in manifests2]
    assert ids == ids2


def test_tier_filtering(registry_file):
    """Test filtering by tier."""
    # Allow only tier 1
    loader = MCPRegistryLoader(registry_path=registry_file, allowed_tiers=[1])
    loader.load()
    
    # Tier 1 tools should be available
    assert loader.has_tool("mcp.github")
    assert loader.has_tool("mcp.fs")
    
    # Tier 2 tool should not be loaded even if enabled
    assert not loader.has_tool("mcp.crypto")
    
    # Get tier 1 tools
    tier1_tools = loader.get_tools_by_tier(1)
    assert len(tier1_tools) == 3
    assert all(m.tier == 1 for m in tier1_tools)


def test_scope_filtering(registry_file):
    """Test filtering by scope."""
    loader = MCPRegistryLoader(registry_path=registry_file)
    loader.load()
    
    # Get tools with 'vcs' scope
    vcs_tools = loader.get_tools_by_scope("vcs")
    assert len(vcs_tools) == 1
    assert vcs_tools[0].id == "mcp.github"
    
    # Get tools with 'fs' scope
    fs_tools = loader.get_tools_by_scope("fs")
    assert len(fs_tools) == 1
    assert fs_tools[0].id == "mcp.fs"
    
    # Get tools with 'web' scope
    web_tools = loader.get_tools_by_scope("web")
    assert len(web_tools) == 1
    assert web_tools[0].id == "mcp.browser"


def test_env_merging(registry_file):
    """Test that environment variables are merged with defaults."""
    loader = MCPRegistryLoader(registry_path=registry_file)
    loader.load()
    
    manifest = loader.get_manifest("mcp.github")
    
    # Should have both default and tool-specific env vars
    assert "AGENT_BUDGET_CEILING" in manifest.env
    assert "GITHUB_TOKEN" in manifest.env
    assert manifest.env["AGENT_BUDGET_CEILING"] == "100"


def test_manifest_to_dict(registry_file):
    """Test converting manifest to dictionary."""
    loader = MCPRegistryLoader(registry_path=registry_file)
    loader.load()
    
    manifest = loader.get_manifest("mcp.github")
    manifest_dict = manifest.to_dict()
    
    assert manifest_dict["id"] == "mcp.github"
    assert manifest_dict["tier"] == 1
    assert manifest_dict["enabled"] is True
    assert manifest_dict["protocol"] == "mcp"
    assert isinstance(manifest_dict["scopes"], list)
    assert isinstance(manifest_dict["env"], dict)


def test_convenience_function(registry_file):
    """Test the convenience load_mcp_registry function."""
    loader = load_mcp_registry(registry_path=registry_file)
    
    assert loader._loaded
    assert loader.has_tool("mcp.github")
    assert len(loader.list_manifests()) > 0


def test_missing_registry_file():
    """Test handling of missing registry file."""
    loader = MCPRegistryLoader(registry_path=Path("/nonexistent/registry.yaml"))
    loader.load()
    
    # Should handle gracefully without crashing
    assert loader._loaded
    assert len(loader.list_manifests()) == 0


def test_invalid_registry_format(tmp_path):
    """Test handling of invalid registry format."""
    invalid_registry = tmp_path / "invalid.yaml"
    invalid_registry.write_text("[ not, a, dict ]")
    
    loader = MCPRegistryLoader(registry_path=invalid_registry)
    
    # YAML that parses to non-dict should raise error
    from src.cuga.tools.mcp_registry import MCPRegistryError
    with pytest.raises(MCPRegistryError):
        loader.load()


def test_disabled_tools_excluded(registry_file):
    """Test that disabled tools are not loaded."""
    loader = MCPRegistryLoader(registry_path=registry_file)
    loader.load()
    
    # mcp.crypto is disabled in the fixture
    assert not loader.has_tool("mcp.crypto")
    
    with pytest.raises(UnregisteredToolError):
        loader.get_manifest("mcp.crypto")


def test_multiple_tier_filtering(registry_file):
    """Test filtering with multiple tiers."""
    # Allow tiers 1 and 2
    loader = MCPRegistryLoader(registry_path=registry_file, allowed_tiers=[1, 2])
    loader.load()
    
    # All tier 1 tools should be available
    tier1_tools = loader.get_tools_by_tier(1)
    assert len(tier1_tools) == 3
    
    # Tier 2 tools that are enabled should be available
    # (mcp.crypto is tier 2 but disabled, so shouldn't be loaded)
    tier2_tools = loader.get_tools_by_tier(2)
    assert len(tier2_tools) == 0


def test_manifest_repr(registry_file):
    """Test manifest string representation."""
    loader = MCPRegistryLoader(registry_path=registry_file)
    loader.load()
    
    manifest = loader.get_manifest("mcp.github")
    repr_str = repr(manifest)
    
    assert "MCPToolManifest" in repr_str
    assert "mcp.github" in repr_str
    assert "tier=1" in repr_str


def test_lazy_loading():
    """Test that loading is lazy and happens only once."""
    loader = MCPRegistryLoader(registry_path=Path("/nonexistent/registry.yaml"))
    
    assert not loader._loaded
    
    # First access should trigger load
    loader.list_manifests()
    assert loader._loaded
    
    # Subsequent accesses should not reload
    loader.list_manifests()
    loader.has_tool("any_tool")


def test_get_tools_by_tier_empty(registry_file):
    """Test get_tools_by_tier with non-existent tier."""
    loader = MCPRegistryLoader(registry_path=registry_file)
    loader.load()
    
    # Tier 99 doesn't exist
    tier99_tools = loader.get_tools_by_tier(99)
    assert len(tier99_tools) == 0


def test_get_tools_by_scope_empty(registry_file):
    """Test get_tools_by_scope with non-existent scope."""
    loader = MCPRegistryLoader(registry_path=registry_file)
    loader.load()
    
    # 'nonexistent' scope doesn't exist
    tools = loader.get_tools_by_scope("nonexistent")
    assert len(tools) == 0
