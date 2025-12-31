"""Tests for Langflow flow import/export idempotence."""

import json
from pathlib import Path

import pytest


class TestLangflowRoundtrip:
    """Test Langflow flow round-trip idempotence."""

    def test_flow_file_exists(self):
        """Test that demo flow file exists."""
        flow_path = Path(__file__).parent.parent / "examples" / "langflow" / "mcp_github_flow.json"
        assert flow_path.exists(), "Demo flow file should exist"

    def test_flow_loads_valid_json(self):
        """Test that flow file contains valid JSON."""
        flow_path = Path(__file__).parent.parent / "examples" / "langflow" / "mcp_github_flow.json"
        
        with open(flow_path) as f:
            data = json.load(f)
        
        assert isinstance(data, dict)
        assert "name" in data
        assert "nodes" in data

    def test_flow_roundtrip_unchanged(self, tmp_path):
        """Test that flow remains unchanged after round-trip."""
        flow_path = Path(__file__).parent.parent / "examples" / "langflow" / "mcp_github_flow.json"
        
        # Load original
        with open(flow_path) as f:
            original = json.load(f)
        
        # Write to temp file
        temp_flow = tmp_path / "temp_flow.json"
        with open(temp_flow, "w") as f:
            json.dump(original, f, indent=2, sort_keys=True)
        
        # Read back
        with open(temp_flow) as f:
            roundtrip = json.load(f)
        
        # Should be identical
        assert original == roundtrip

    def test_flow_has_required_fields(self):
        """Test that flow has required fields."""
        flow_path = Path(__file__).parent.parent / "examples" / "langflow" / "mcp_github_flow.json"
        
        with open(flow_path) as f:
            flow = json.load(f)
        
        # Required top-level fields
        assert "name" in flow
        assert "nodes" in flow
        assert "edges" in flow
        
        # Should have at least one node
        assert len(flow["nodes"]) > 0
        
        # Check node structure
        for node in flow["nodes"]:
            assert "id" in node
            assert "type" in node
            assert "data" in node

    def test_flow_deterministic_export(self):
        """Test that flow export is deterministic."""
        flow_path = Path(__file__).parent.parent / "examples" / "langflow" / "mcp_github_flow.json"
        
        with open(flow_path) as f:
            flow = json.load(f)
        
        # Export multiple times
        exports = []
        for _ in range(3):
            exported = json.dumps(flow, indent=2, sort_keys=True)
            exports.append(exported)
        
        # All exports should be identical
        first_export = exports[0]
        for export in exports[1:]:
            assert export == first_export


class TestFlowStructure:
    """Test flow structure and components."""

    def test_flow_has_mcp_client(self):
        """Test that flow includes MCP client component."""
        flow_path = Path(__file__).parent.parent / "examples" / "langflow" / "mcp_github_flow.json"
        
        with open(flow_path) as f:
            flow = json.load(f)
        
        # Check for MCP client node
        mcp_nodes = [n for n in flow["nodes"] if n["type"] == "MCPClient"]
        assert len(mcp_nodes) > 0, "Flow should contain at least one MCP client node"

    def test_flow_node_connections(self):
        """Test that flow nodes are properly connected."""
        flow_path = Path(__file__).parent.parent / "examples" / "langflow" / "mcp_github_flow.json"
        
        with open(flow_path) as f:
            flow = json.load(f)
        
        if "edges" in flow and len(flow["edges"]) > 0:
            for edge in flow["edges"]:
                assert "source" in edge
                assert "target" in edge
                
                # Source and target should exist in nodes
                node_ids = [n["id"] for n in flow["nodes"]]
                assert edge["source"] in node_ids
                assert edge["target"] in node_ids
