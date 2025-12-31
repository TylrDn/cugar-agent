"""Tests for Langflow MCP Client Component."""

from pathlib import Path
import pytest

from cuga.langflow_components.mcp_client import MCPClientComponent


@pytest.fixture
def sample_registry(tmp_path):
    """Create a sample registry file for testing."""
    import yaml
    
    registry_path = tmp_path / "registry.yaml"
    with open(registry_path, "w") as f:
        yaml.safe_dump({
            "version": "v1",
            "entries": [
                {
                    "id": "mcp.github",
                    "tier": 1,
                    "enabled": True,
                    "ref": "docker://github",
                },
                {
                    "id": "mcp.crypto",
                    "tier": 2,
                    "enabled": True,
                    "ref": "docker://crypto",
                },
            ],
        }, f)
    
    return registry_path


class TestMCPClientComponent:
    """Test MCPClientComponent."""

    def test_component_creation(self):
        """Test creating an MCP client component."""
        component = MCPClientComponent(
            mcp_servers="registry.yaml",
            allowed_tiers=[1, 2],
            deny_by_default=True,
        )
        
        assert component.mcp_servers == "registry.yaml"
        assert component.allowed_tiers == [1, 2]
        assert component.deny_by_default is True
        assert component._loaded is False

    def test_component_build(self, sample_registry):
        """Test building the component."""
        component = MCPClientComponent(
            mcp_servers=str(sample_registry),
            allowed_tiers=[1, 2],
        )
        
        result = component.build()
        
        assert "tools" in result
        assert "tool_ids" in result
        assert "statistics" in result
        assert component._loaded is True

    def test_component_tool_ids(self, sample_registry):
        """Test listing tool IDs."""
        component = MCPClientComponent(
            mcp_servers=str(sample_registry),
            allowed_tiers=[1, 2],
        )
        
        component.build()
        tool_ids = component.list_tool_ids()
        
        assert isinstance(tool_ids, list)
        assert len(tool_ids) == 2
        assert tool_ids == sorted(tool_ids)  # Deterministic ordering

    def test_component_tier_filtering(self, sample_registry):
        """Test tier filtering works correctly."""
        # Only tier 1
        component = MCPClientComponent(
            mcp_servers=str(sample_registry),
            allowed_tiers=[1],
        )
        
        result = component.build()
        
        assert len(result["tool_ids"]) == 1
        assert "mcp.github" in result["tool_ids"]
        assert "mcp.crypto" not in result["tool_ids"]

    def test_component_statistics(self, sample_registry):
        """Test statistics generation."""
        component = MCPClientComponent(
            mcp_servers=str(sample_registry),
            allowed_tiers=[1, 2],
        )
        
        result = component.build()
        stats = result["statistics"]
        
        assert "total_tools" in stats
        assert "allowed_tiers" in stats
        assert "tiers" in stats
        assert stats["total_tools"] == 2
        assert stats["allowed_tiers"] == [1, 2]

    def test_execute_tool_before_build(self):
        """Test executing tool before building raises error."""
        component = MCPClientComponent()
        
        with pytest.raises(RuntimeError, match="not loaded"):
            component.execute_tool("mcp.github", {})

    def test_execute_tool_after_build(self, sample_registry):
        """Test executing tool after building."""
        component = MCPClientComponent(
            mcp_servers=str(sample_registry),
            allowed_tiers=[1],
        )
        
        component.build()
        result = component.execute_tool("mcp.github", {"repo": "test"})
        
        assert result is not None
        assert result["tool"] == "mcp.github"

    def test_component_metadata(self):
        """Test component metadata is defined."""
        from cuga.langflow_components.mcp_client import component_metadata
        
        assert component_metadata["display_name"] == "MCP Client"
        assert "inputs" in component_metadata
        assert "outputs" in component_metadata
        assert len(component_metadata["inputs"]) == 4
        assert len(component_metadata["outputs"]) == 3


class TestComponentIntegration:
    """Test component integration scenarios."""

    def test_multiple_components_isolated(self, sample_registry):
        """Test that multiple components are isolated."""
        component1 = MCPClientComponent(
            mcp_servers=str(sample_registry),
            allowed_tiers=[1],
        )
        component2 = MCPClientComponent(
            mcp_servers=str(sample_registry),
            allowed_tiers=[1, 2],
        )
        
        result1 = component1.build()
        result2 = component2.build()
        
        assert len(result1["tool_ids"]) == 1
        assert len(result2["tool_ids"]) == 2

    def test_component_with_invalid_registry(self):
        """Test component with invalid registry file."""
        component = MCPClientComponent(
            mcp_servers="/nonexistent/registry.yaml",
            allowed_tiers=[1],
        )
        
        result = component.build()
        
        # Should handle gracefully
        assert result["tool_ids"] == []
        assert result["statistics"]["total_tools"] == 0
