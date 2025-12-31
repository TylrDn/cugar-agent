"""Tests for Langflow MCP components."""

import tempfile
from pathlib import Path

import pytest

from cuga.langflow_components.mcp_client import (
    MCPClientComponent,
    MCPToolExecutorComponent,
    create_mcp_langflow_components,
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
  env: {}
  mounts: []
  budget_policy: warn

entries:
  - id: mcp.github
    ref: docker://github
    scopes: [vcs]
    mounts: []
  
  - id: mcp.fs
    ref: docker://filesystem
    scopes: [fs]
    mounts: []
  
  - id: mcp.browser
    tier: 2
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


def test_mcp_client_component_initialization():
    """Test MCPClientComponent can be instantiated."""
    component = MCPClientComponent()
    assert component is not None
    assert component.display_name == "MCP Client"


def test_mcp_client_component_config():
    """Test component configuration."""
    component = MCPClientComponent()
    config = component.build_config()
    
    assert "registry_path" in config
    assert "allowed_tiers" in config
    assert "tool_ids" in config
    assert "enable_guards" in config
    assert "enable_audit" in config


def test_mcp_client_component_execution(registry_file):
    """Test component execution with default settings."""
    component = MCPClientComponent()
    
    result = component(
        registry_path=str(registry_file),
        allowed_tiers="1",
        enable_guards=True,
        enable_audit=False,
    )
    
    assert "tools" in result
    assert "toolbox" in result
    assert "tool_count" in result
    assert result["tool_count"] >= 2
    assert len(result["tools"]) >= 2


def test_mcp_client_component_tier_filtering(registry_file):
    """Test tier-based filtering."""
    component = MCPClientComponent()
    
    # Only tier 1
    result = component(
        registry_path=str(registry_file),
        allowed_tiers="1",
        enable_audit=False,
    )
    
    tool_ids = [t["id"] for t in result["tools"]]
    assert "mcp.github" in tool_ids
    assert "mcp.fs" in tool_ids
    assert "mcp.browser" not in tool_ids  # tier 2
    
    # Both tiers
    result_all = component(
        registry_path=str(registry_file),
        allowed_tiers="1,2",
        enable_audit=False,
    )
    
    tool_ids_all = [t["id"] for t in result_all["tools"]]
    assert "mcp.github" in tool_ids_all
    assert "mcp.browser" in tool_ids_all


def test_mcp_client_component_tool_filtering(registry_file):
    """Test filtering specific tools."""
    component = MCPClientComponent()
    
    result = component(
        registry_path=str(registry_file),
        allowed_tiers="1",
        tool_ids="mcp.github",
        enable_audit=False,
    )
    
    tool_ids = [t["id"] for t in result["tools"]]
    assert len(tool_ids) == 1
    assert "mcp.github" in tool_ids


def test_mcp_client_component_multiple_tools(registry_file):
    """Test filtering multiple specific tools."""
    component = MCPClientComponent()
    
    result = component(
        registry_path=str(registry_file),
        allowed_tiers="1",
        tool_ids="mcp.github,mcp.fs",
        enable_audit=False,
    )
    
    tool_ids = [t["id"] for t in result["tools"]]
    assert len(tool_ids) == 2
    assert "mcp.github" in tool_ids
    assert "mcp.fs" in tool_ids


def test_mcp_client_component_tool_metadata(registry_file):
    """Test tool metadata is correct."""
    component = MCPClientComponent()
    
    result = component(
        registry_path=str(registry_file),
        allowed_tiers="1",
        enable_audit=False,
    )
    
    # Find github tool
    github_tool = next((t for t in result["tools"] if t["id"] == "mcp.github"), None)
    assert github_tool is not None
    assert github_tool["tier"] == 1
    assert github_tool["protocol"] == "mcp"
    assert github_tool["sandbox"] == "py-slim"
    assert "vcs" in github_tool["scopes"]


def test_mcp_tool_executor_component_initialization():
    """Test MCPToolExecutorComponent can be instantiated."""
    component = MCPToolExecutorComponent()
    assert component is not None
    assert component.display_name == "MCP Tool Executor"


def test_mcp_tool_executor_component_config():
    """Test executor component configuration."""
    component = MCPToolExecutorComponent()
    config = component.build_config()
    
    assert "toolbox" in config
    assert "tool_id" in config
    assert "inputs" in config
    assert "context" in config


def test_mcp_tool_executor_component_execution(registry_file):
    """Test tool execution via executor component."""
    # First create a client and toolbox
    client = MCPClientComponent()
    client_result = client(
        registry_path=str(registry_file),
        allowed_tiers="1",
        enable_audit=False,
    )
    
    toolbox = client_result["toolbox"]
    
    # Register a mock handler
    def mock_handler(inputs, context):
        return {"status": "ok", "data": inputs.get("test")}
    
    toolbox.register_handler("mcp.github", mock_handler)
    
    # Execute via executor component
    executor = MCPToolExecutorComponent()
    result = executor(
        toolbox=toolbox,
        tool_id="mcp.github",
        inputs={"test": "value"},
        context={"trace_id": "test-123"},
    )
    
    assert result["status"] == "success"
    assert result["tool_id"] == "mcp.github"
    assert result["result"]["status"] == "ok"
    assert result["result"]["data"] == "value"


def test_mcp_tool_executor_component_error_handling(registry_file):
    """Test error handling in executor component."""
    # Create client and toolbox
    client = MCPClientComponent()
    client_result = client(
        registry_path=str(registry_file),
        allowed_tiers="1",
        enable_audit=False,
    )
    
    toolbox = client_result["toolbox"]
    
    # Register a failing handler
    def failing_handler(inputs, context):
        raise ValueError("Test error")
    
    toolbox.register_handler("mcp.github", failing_handler)
    
    # Execute via executor component
    executor = MCPToolExecutorComponent()
    result = executor(
        toolbox=toolbox,
        tool_id="mcp.github",
        inputs={},
    )
    
    assert result["status"] == "error"
    assert result["tool_id"] == "mcp.github"
    assert "Test error" in result["error"]


def test_mcp_tool_executor_with_context(registry_file):
    """Test that context is passed to tool execution."""
    client = MCPClientComponent()
    client_result = client(
        registry_path=str(registry_file),
        allowed_tiers="1",
        enable_audit=False,
    )
    
    toolbox = client_result["toolbox"]
    
    received_context = {}
    
    def context_handler(inputs, context):
        received_context.update(context)
        return {"status": "ok"}
    
    toolbox.register_handler("mcp.github", context_handler)
    
    executor = MCPToolExecutorComponent()
    result = executor(
        toolbox=toolbox,
        tool_id="mcp.github",
        inputs={},
        context={"trace_id": "test-456", "user_id": "user-789"},
    )
    
    assert result["status"] == "success"
    assert received_context.get("trace_id") == "test-456"
    assert received_context.get("user_id") == "user-789"


def test_create_mcp_langflow_components():
    """Test factory function returns component classes."""
    components = create_mcp_langflow_components()
    
    assert len(components) == 2
    assert MCPClientComponent in components
    assert MCPToolExecutorComponent in components


def test_mcp_client_component_default_registry():
    """Test component works with default registry path."""
    component = MCPClientComponent()
    
    # Should not crash even if default registry doesn't exist
    result = component(
        allowed_tiers="1",
        enable_audit=False,
    )
    
    # Should return valid structure even with empty tools
    assert "tools" in result
    assert "toolbox" in result
    assert isinstance(result["tools"], list)


def test_mcp_client_component_invalid_tiers(registry_file):
    """Test handling of invalid tier values."""
    component = MCPClientComponent()
    
    # Invalid tier string should default to tier 1
    result = component(
        registry_path=str(registry_file),
        allowed_tiers="invalid,garbage",
        enable_audit=False,
    )
    
    assert "tools" in result
    # Should still work with default tier


def test_mcp_client_component_empty_tool_ids(registry_file):
    """Test handling of empty tool_ids."""
    component = MCPClientComponent()
    
    # Empty string should load all tools
    result = component(
        registry_path=str(registry_file),
        allowed_tiers="1",
        tool_ids="",
        enable_audit=False,
    )
    
    assert len(result["tools"]) >= 2


def test_mcp_client_component_nonexistent_tools(registry_file):
    """Test filtering for nonexistent tools."""
    component = MCPClientComponent()
    
    result = component(
        registry_path=str(registry_file),
        allowed_tiers="1",
        tool_ids="mcp.nonexistent,mcp.alsonotreal",
        enable_audit=False,
    )
    
    # Should return empty list or only valid tools
    assert isinstance(result["tools"], list)


def test_full_workflow(registry_file):
    """Test a complete workflow with client and executor."""
    # Step 1: Create client and load tools
    client = MCPClientComponent()
    client_result = client(
        registry_path=str(registry_file),
        allowed_tiers="1",
        tool_ids="mcp.github,mcp.fs",
        enable_guards=True,
        enable_audit=False,
    )
    
    assert len(client_result["tools"]) == 2
    toolbox = client_result["toolbox"]
    
    # Step 2: Register handlers
    def github_handler(inputs, context):
        return {"repo": inputs.get("repo"), "action": "cloned"}
    
    def fs_handler(inputs, context):
        return {"file": inputs.get("file"), "action": "read"}
    
    toolbox.register_handler("mcp.github", github_handler)
    toolbox.register_handler("mcp.fs", fs_handler)
    
    # Step 3: Execute multiple tools
    executor = MCPToolExecutorComponent()
    
    result1 = executor(
        toolbox=toolbox,
        tool_id="mcp.github",
        inputs={"repo": "test/repo"},
    )
    
    result2 = executor(
        toolbox=toolbox,
        tool_id="mcp.fs",
        inputs={"file": "test.txt"},
    )
    
    # Verify both executions
    assert result1["status"] == "success"
    assert result1["result"]["repo"] == "test/repo"
    assert result1["result"]["action"] == "cloned"
    
    assert result2["status"] == "success"
    assert result2["result"]["file"] == "test.txt"
    assert result2["result"]["action"] == "read"
