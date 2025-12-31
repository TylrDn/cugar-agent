"""Tests for MCP registry loader with tier-based security."""

from pathlib import Path
from typing import List

import pytest

from cuga.tools.mcp_registry import (
    MCPRegistryLoader,
    MCPRegistryManifest,
    MCPToolEntry,
    get_registry,
    load_mcp_manifest,
)


@pytest.fixture
def sample_registry_data():
    """Sample registry data for testing."""
    return {
        "version": "v1",
        "defaults": {
            "tier": 1,
            "enabled": True,
            "protocol": "mcp",
            "sandbox": "py-slim",
            "scopes": [],
            "env": {},
            "mounts": [],
            "budget_policy": "warn",
        },
        "entries": [
            {
                "id": "mcp.github",
                "tier": 1,
                "enabled": True,
                "ref": "docker://github",
                "scopes": ["vcs"],
                "env": {"GITHUB_TOKEN": "${GITHUB_TOKEN:?}"},
            },
            {
                "id": "mcp.crypto",
                "tier": 2,
                "enabled": False,
                "sandbox": "py-full",
                "ref": "docker://crypto",
                "scopes": ["finance"],
            },
            {
                "id": "mcp.admin",
                "tier": 3,
                "enabled": False,
                "sandbox": "orchestrator",
                "ref": "http://admin:8080",
                "scopes": ["admin"],
            },
        ],
    }


@pytest.fixture
def temp_registry_file(tmp_path, sample_registry_data):
    """Create a temporary registry file for testing."""
    import yaml

    registry_path = tmp_path / "registry.yaml"
    with open(registry_path, "w") as f:
        yaml.safe_dump(sample_registry_data, f)
    return registry_path


class TestMCPToolEntry:
    """Test MCPToolEntry dataclass."""

    def test_tool_entry_creation(self):
        """Test creating a tool entry with defaults."""
        entry = MCPToolEntry(id="test.tool")
        assert entry.id == "test.tool"
        assert entry.tier == 1
        assert entry.enabled is True
        assert entry.protocol == "mcp"
        assert entry.sandbox == "py-slim"
        assert entry.scopes == []
        assert entry.env == {}
        assert entry.mounts == []
        assert entry.budget_policy == "warn"

    def test_get_tier_name(self):
        """Test tier name conversion."""
        entry1 = MCPToolEntry(id="tool1", tier=1)
        entry2 = MCPToolEntry(id="tool2", tier=2)
        entry3 = MCPToolEntry(id="tool3", tier=3)

        assert entry1.get_tier_name() == "sandbox"
        assert entry2.get_tier_name() == "restricted"
        assert entry3.get_tier_name() == "trusted"

    def test_is_allowed_enabled_flag(self):
        """Test is_allowed with enabled flag."""
        enabled_tool = MCPToolEntry(id="tool", enabled=True)
        disabled_tool = MCPToolEntry(id="tool", enabled=False)

        assert enabled_tool.is_allowed() is True
        assert disabled_tool.is_allowed() is False

    def test_is_allowed_tier_filtering(self):
        """Test is_allowed with tier filtering."""
        tier1_tool = MCPToolEntry(id="tool1", tier=1, enabled=True)
        tier2_tool = MCPToolEntry(id="tool2", tier=2, enabled=True)
        tier3_tool = MCPToolEntry(id="tool3", tier=3, enabled=True)

        # Tier 1 request allows only tier 1
        assert tier1_tool.is_allowed(requested_tier=1) is True
        assert tier2_tool.is_allowed(requested_tier=1) is False
        assert tier3_tool.is_allowed(requested_tier=1) is False

        # Tier 2 request allows tier 1 and 2
        assert tier1_tool.is_allowed(requested_tier=2) is True
        assert tier2_tool.is_allowed(requested_tier=2) is True
        assert tier3_tool.is_allowed(requested_tier=2) is False

        # Tier 3 request allows all
        assert tier1_tool.is_allowed(requested_tier=3) is True
        assert tier2_tool.is_allowed(requested_tier=3) is True
        assert tier3_tool.is_allowed(requested_tier=3) is True


class TestMCPRegistryManifest:
    """Test MCPRegistryManifest."""

    def test_manifest_creation(self):
        """Test creating an empty manifest."""
        manifest = MCPRegistryManifest()
        assert manifest.version == "v1"
        assert manifest.defaults == {}
        assert manifest.entries == []

    def test_get_tool(self):
        """Test getting a tool by ID."""
        entry1 = MCPToolEntry(id="tool1")
        entry2 = MCPToolEntry(id="tool2")
        manifest = MCPRegistryManifest(entries=[entry1, entry2])

        found = manifest.get_tool("tool1")
        assert found is not None
        assert found.id == "tool1"

        not_found = manifest.get_tool("tool3")
        assert not_found is None

    def test_list_tools_deterministic_sorting(self):
        """Test that list_tools returns deterministically sorted results."""
        # Create tools in non-alphabetical order
        entries = [
            MCPToolEntry(id="zebra", tier=1, enabled=True),
            MCPToolEntry(id="alpha", tier=1, enabled=True),
            MCPToolEntry(id="beta", tier=1, enabled=True),
        ]
        manifest = MCPRegistryManifest(entries=entries)

        tools = manifest.list_tools(sorted_by_id=True)
        ids = [t.id for t in tools]
        assert ids == ["alpha", "beta", "zebra"]

    def test_list_tools_tier_filtering(self):
        """Test filtering tools by tier."""
        entries = [
            MCPToolEntry(id="tier1", tier=1, enabled=True),
            MCPToolEntry(id="tier2", tier=2, enabled=True),
            MCPToolEntry(id="tier3", tier=3, enabled=True),
        ]
        manifest = MCPRegistryManifest(entries=entries)

        tier1_tools = manifest.list_tools(tier=1)
        assert len(tier1_tools) == 1
        assert tier1_tools[0].id == "tier1"

        tier2_tools = manifest.list_tools(tier=2)
        assert len(tier2_tools) == 2
        assert set(t.id for t in tier2_tools) == {"tier1", "tier2"}

        tier3_tools = manifest.list_tools(tier=3)
        assert len(tier3_tools) == 3

    def test_list_tools_enabled_filtering(self):
        """Test filtering by enabled flag."""
        entries = [
            MCPToolEntry(id="enabled", tier=1, enabled=True),
            MCPToolEntry(id="disabled", tier=1, enabled=False),
        ]
        manifest = MCPRegistryManifest(entries=entries)

        enabled_only = manifest.list_tools(enabled_only=True)
        assert len(enabled_only) == 1
        assert enabled_only[0].id == "enabled"

        all_tools = manifest.list_tools(enabled_only=False)
        assert len(all_tools) == 2

    def test_get_tier_counts(self):
        """Test counting tools per tier."""
        entries = [
            MCPToolEntry(id="t1a", tier=1),
            MCPToolEntry(id="t1b", tier=1),
            MCPToolEntry(id="t2a", tier=2),
            MCPToolEntry(id="t3a", tier=3),
        ]
        manifest = MCPRegistryManifest(entries=entries)

        counts = manifest.get_tier_counts()
        assert counts == {1: 2, 2: 1, 3: 1}


class TestMCPRegistryLoader:
    """Test MCPRegistryLoader."""

    def test_loader_with_temp_file(self, temp_registry_file):
        """Test loading from a temporary registry file."""
        loader = MCPRegistryLoader(registry_path=temp_registry_file, deny_by_default=False)
        manifest = loader.load()

        assert manifest.version == "v1"
        assert len(manifest.entries) == 3

        # Check entries are sorted by ID
        ids = [e.id for e in manifest.entries]
        assert ids == sorted(ids)

    def test_deny_by_default_true(self, temp_registry_file):
        """Test that deny_by_default filters out disabled tools."""
        loader = MCPRegistryLoader(registry_path=temp_registry_file, deny_by_default=True)
        manifest = loader.load()

        # Only mcp.github should be loaded (enabled=True)
        assert len(manifest.entries) == 1
        assert manifest.entries[0].id == "mcp.github"

    def test_deny_by_default_false(self, temp_registry_file):
        """Test that deny_by_default=False loads all tools."""
        loader = MCPRegistryLoader(registry_path=temp_registry_file, deny_by_default=False)
        manifest = loader.load()

        # All 3 tools should be loaded
        assert len(manifest.entries) == 3

    def test_missing_registry_file(self, tmp_path):
        """Test handling of missing registry file."""
        missing_path = tmp_path / "nonexistent.yaml"
        loader = MCPRegistryLoader(registry_path=missing_path)
        manifest = loader.load()

        # Should return empty manifest without error
        assert len(manifest.entries) == 0

    def test_duplicate_id_validation(self, tmp_path):
        """Test that duplicate IDs are rejected."""
        import yaml

        data = {
            "version": "v1",
            "entries": [
                {"id": "duplicate", "tier": 1},
                {"id": "duplicate", "tier": 2},
            ],
        }

        registry_path = tmp_path / "duplicate.yaml"
        with open(registry_path, "w") as f:
            yaml.safe_dump(data, f)

        loader = MCPRegistryLoader(registry_path=registry_path, deny_by_default=False)

        with pytest.raises(RuntimeError, match="Duplicate tool IDs"):
            loader.load()

    def test_invalid_tier_handling(self, tmp_path):
        """Test that invalid tier numbers are handled."""
        import yaml

        data = {
            "version": "v1",
            "entries": [
                {"id": "bad_tier", "tier": 99, "enabled": True},
            ],
        }

        registry_path = tmp_path / "bad_tier.yaml"
        with open(registry_path, "w") as f:
            yaml.safe_dump(data, f)

        loader = MCPRegistryLoader(registry_path=registry_path, deny_by_default=False)
        manifest = loader.load()

        # Should default to tier 1
        assert manifest.entries[0].tier == 1

    def test_reload(self, temp_registry_file):
        """Test reloading the registry."""
        loader = MCPRegistryLoader(registry_path=temp_registry_file, deny_by_default=False)
        manifest1 = loader.load()
        assert len(manifest1.entries) == 3

        # Reload should work
        manifest2 = loader.reload()
        assert len(manifest2.entries) == 3
        assert manifest1 is not manifest2

    def test_get_manifest_cached(self, temp_registry_file):
        """Test that get_manifest returns cached manifest."""
        loader = MCPRegistryLoader(registry_path=temp_registry_file)
        loader.load()

        cached = loader.get_manifest()
        assert cached is not None
        assert len(cached.entries) > 0


class TestGlobalRegistry:
    """Test global registry functions."""

    def test_get_registry_singleton(self):
        """Test that get_registry returns the same instance."""
        # Reset global state
        import cuga.tools.mcp_registry as reg_module

        reg_module._global_registry = None

        registry1 = get_registry()
        registry2 = get_registry()

        assert registry1 is registry2

    def test_load_mcp_manifest(self, temp_registry_file, monkeypatch):
        """Test load_mcp_manifest convenience function."""
        # Reset global state
        import cuga.tools.mcp_registry as reg_module

        reg_module._global_registry = None

        manifest = load_mcp_manifest(temp_registry_file)
        assert manifest.version == "v1"
        assert len(manifest.entries) >= 1


class TestDeterministicBehavior:
    """Test deterministic behavior across registry operations."""

    def test_consistent_sorting_across_loads(self, temp_registry_file):
        """Test that multiple loads produce identical sorted output."""
        loader1 = MCPRegistryLoader(registry_path=temp_registry_file, deny_by_default=False)
        loader2 = MCPRegistryLoader(registry_path=temp_registry_file, deny_by_default=False)

        manifest1 = loader1.load()
        manifest2 = loader2.load()

        ids1 = [e.id for e in manifest1.entries]
        ids2 = [e.id for e in manifest2.entries]

        assert ids1 == ids2
        assert ids1 == sorted(ids1)

    def test_list_tools_stable_ordering(self, temp_registry_file):
        """Test that list_tools produces stable ordering."""
        loader = MCPRegistryLoader(registry_path=temp_registry_file, deny_by_default=False)
        manifest = loader.load()

        # Call list_tools multiple times
        result1 = manifest.list_tools()
        result2 = manifest.list_tools()
        result3 = manifest.list_tools()

        ids1 = [t.id for t in result1]
        ids2 = [t.id for t in result2]
        ids3 = [t.id for t in result3]

        assert ids1 == ids2 == ids3
        assert ids1 == sorted(ids1)
