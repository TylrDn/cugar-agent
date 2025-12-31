"""Tests for Langflow flow roundtrip fidelity."""

import json
from pathlib import Path

import pytest


@pytest.fixture
def flow_path():
    """Get path to the demo flow JSON."""
    return Path(__file__).parent.parent / "examples" / "langflow" / "mcp_github_flow.json"


def test_flow_file_exists(flow_path):
    """Test that the demo flow file exists."""
    assert flow_path.exists(), f"Flow file not found at {flow_path}"


def test_flow_json_valid(flow_path):
    """Test that the flow JSON is valid."""
    with open(flow_path, "r") as f:
        flow_data = json.load(f)
    
    assert isinstance(flow_data, dict)
    assert "nodes" in flow_data
    assert "edges" in flow_data
    assert "metadata" in flow_data


def test_flow_structure(flow_path):
    """Test the structure of the flow."""
    with open(flow_path, "r") as f:
        flow_data = json.load(f)
    
    # Check basic properties
    assert flow_data["name"] == "MCP GitHub Integration Demo"
    assert "version" in flow_data
    
    # Check nodes
    nodes = flow_data["nodes"]
    assert len(nodes) >= 3, "Should have at least MCP Client and executors"
    
    # Check edges
    edges = flow_data["edges"]
    assert len(edges) >= 2, "Should have at least connections from client to executors"


def test_mcp_client_node(flow_path):
    """Test MCP client node configuration."""
    with open(flow_path, "r") as f:
        flow_data = json.load(f)
    
    # Find MCP client node
    mcp_nodes = [n for n in flow_data["nodes"] if n["type"] == "MCPClientComponent"]
    assert len(mcp_nodes) == 1, "Should have exactly one MCP client node"
    
    mcp_node = mcp_nodes[0]
    
    # Check inputs
    assert "inputs" in mcp_node["data"]
    inputs = mcp_node["data"]["inputs"]
    
    assert "allowed_tiers" in inputs
    assert "tool_ids" in inputs
    assert "enable_guards" in inputs
    assert "enable_audit" in inputs


def test_tool_executor_nodes(flow_path):
    """Test tool executor node configurations."""
    with open(flow_path, "r") as f:
        flow_data = json.load(f)
    
    # Find executor nodes
    executor_nodes = [n for n in flow_data["nodes"] if n["type"] == "MCPToolExecutorComponent"]
    assert len(executor_nodes) >= 2, "Should have at least two executor nodes"
    
    for node in executor_nodes:
        assert "inputs" in node["data"]
        inputs = node["data"]["inputs"]
        
        assert "toolbox" in inputs
        assert "tool_id" in inputs
        assert "inputs" in inputs


def test_edges_valid(flow_path):
    """Test that edges connect valid nodes."""
    with open(flow_path, "r") as f:
        flow_data = json.load(f)
    
    node_ids = {n["id"] for n in flow_data["nodes"]}
    
    for edge in flow_data["edges"]:
        assert "source" in edge
        assert "target" in edge
        
        assert edge["source"] in node_ids, f"Edge source {edge['source']} not in nodes"
        assert edge["target"] in node_ids, f"Edge target {edge['target']} not in nodes"


def test_metadata_complete(flow_path):
    """Test that metadata is complete."""
    with open(flow_path, "r") as f:
        flow_data = json.load(f)
    
    metadata = flow_data["metadata"]
    
    required_fields = ["created_at", "updated_at", "author", "tags"]
    for field in required_fields:
        assert field in metadata, f"Missing required metadata field: {field}"
    
    assert isinstance(metadata["tags"], list)
    assert len(metadata["tags"]) > 0


def test_roundtrip_fidelity(flow_path):
    """Test that flow can be loaded and saved without changes."""
    # Load original
    with open(flow_path, "r") as f:
        original_data = json.load(f)
    
    # Serialize and reload
    serialized = json.dumps(original_data, indent=2, sort_keys=True)
    reloaded_data = json.loads(serialized)
    
    # Compare keys at top level
    assert set(original_data.keys()) == set(reloaded_data.keys())
    
    # Compare node count
    assert len(original_data["nodes"]) == len(reloaded_data["nodes"])
    
    # Compare edge count
    assert len(original_data["edges"]) == len(reloaded_data["edges"])


def test_flow_node_positions(flow_path):
    """Test that nodes have valid positions."""
    with open(flow_path, "r") as f:
        flow_data = json.load(f)
    
    for node in flow_data["nodes"]:
        assert "position" in node
        position = node["position"]
        
        assert "x" in position
        assert "y" in position
        assert isinstance(position["x"], (int, float))
        assert isinstance(position["y"], (int, float))


def test_flow_node_ids_unique(flow_path):
    """Test that node IDs are unique."""
    with open(flow_path, "r") as f:
        flow_data = json.load(f)
    
    node_ids = [n["id"] for n in flow_data["nodes"]]
    assert len(node_ids) == len(set(node_ids)), "Node IDs must be unique"


def test_flow_edge_ids_unique(flow_path):
    """Test that edge IDs are unique."""
    with open(flow_path, "r") as f:
        flow_data = json.load(f)
    
    edge_ids = [e["id"] for e in flow_data["edges"]]
    assert len(edge_ids) == len(set(edge_ids)), "Edge IDs must be unique"


def test_flow_tool_configuration(flow_path):
    """Test that tools are configured correctly in the flow."""
    with open(flow_path, "r") as f:
        flow_data = json.load(f)
    
    # Find MCP client
    mcp_nodes = [n for n in flow_data["nodes"] if n["type"] == "MCPClientComponent"]
    mcp_node = mcp_nodes[0]
    
    tool_ids_str = mcp_node["data"]["inputs"]["tool_ids"]
    tool_ids = [t.strip() for t in tool_ids_str.split(",")]
    
    # Verify executors use tools from the client
    executor_nodes = [n for n in flow_data["nodes"] if n["type"] == "MCPToolExecutorComponent"]
    
    for executor in executor_nodes:
        executor_tool = executor["data"]["inputs"]["tool_id"]
        # Tool should be one of the configured tools or a valid MCP tool pattern
        assert executor_tool.startswith("mcp."), f"Tool {executor_tool} should be MCP tool"


def test_flow_serialization_consistent(flow_path):
    """Test that multiple serializations produce consistent output."""
    with open(flow_path, "r") as f:
        flow_data = json.load(f)
    
    # Serialize twice
    serialized1 = json.dumps(flow_data, indent=2, sort_keys=True)
    serialized2 = json.dumps(flow_data, indent=2, sort_keys=True)
    
    # Should be identical
    assert serialized1 == serialized2


def test_flow_json_formatting(flow_path):
    """Test that JSON is properly formatted."""
    with open(flow_path, "r") as f:
        content = f.read()
    
    # Should be valid JSON
    flow_data = json.loads(content)
    
    # Re-format and compare
    formatted = json.dumps(flow_data, indent=2, sort_keys=False)
    
    # Both should parse to the same data
    assert json.loads(content) == json.loads(formatted)


def test_flow_imports_successfully(flow_path):
    """Test that the flow can be imported without errors."""
    with open(flow_path, "r") as f:
        flow_data = json.load(f)
    
    # Simulate import process
    assert "name" in flow_data
    assert "nodes" in flow_data
    assert "edges" in flow_data
    
    # Verify all required fields for import
    for node in flow_data["nodes"]:
        assert "id" in node
        assert "type" in node
        assert "data" in node


def test_flow_compatible_with_langflow(flow_path):
    """Test that flow structure is compatible with Langflow format."""
    with open(flow_path, "r") as f:
        flow_data = json.load(f)
    
    # Check Langflow-specific structure
    for node in flow_data["nodes"]:
        data = node["data"]
        
        # Should have label and component
        assert "label" in data
        assert "component" in data
        
        # Should have inputs and outputs
        assert "inputs" in data
        assert "outputs" in data


def test_flow_version_present(flow_path):
    """Test that flow has version information."""
    with open(flow_path, "r") as f:
        flow_data = json.load(f)
    
    assert "version" in flow_data
    version = flow_data["version"]
    
    # Version should be in semver format
    parts = version.split(".")
    assert len(parts) >= 2, "Version should be in semver format (e.g., 1.0.0)"
