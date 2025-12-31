"""Tests for MCP toolbox functionality."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cuga.observability.mcp_audit import MCPAuditLogger
from cuga.tools.mcp_registry import MCPToolManifest
from cuga.tools.mcp_toolbox import (
    GuardCheckError,
    MCPToolbox,
    MCPToolboxError,
    MCPToolWrapper,
    ToolExecutionError,
    budget_guard,
    create_toolbox,
    sandbox_guard,
    tier_guard,
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
    mounts: [/workspace:ro]
  
  - id: mcp.browser
    sandbox: node-full
    ref: docker://browser
    scopes: [web]
    budget_policy: block
    mounts: []
"""


@pytest.fixture
def registry_file(sample_registry_yaml, tmp_path):
    """Create a temporary registry file."""
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(sample_registry_yaml)
    return registry_path


@pytest.fixture
def audit_log_path(tmp_path):
    """Create a temporary audit log path."""
    return tmp_path / "audit.jsonl"


def test_toolbox_initialization(registry_file):
    """Test toolbox initialization and loading."""
    toolbox = MCPToolbox(registry_path=registry_file, enable_audit=False)
    toolbox.load_tools()
    
    # Should load all enabled tools
    tools = toolbox.list_tools()
    assert len(tools) == 3
    assert "mcp.github" in tools
    assert "mcp.fs" in tools
    assert "mcp.browser" in tools


def test_toolbox_tier_filtering(registry_file):
    """Test toolbox with tier filtering."""
    # Only load tier 1 tools
    toolbox = MCPToolbox(
        registry_path=registry_file,
        allowed_tiers=[1],
        enable_audit=False,
    )
    toolbox.load_tools()
    
    tools = toolbox.list_tools()
    assert len(tools) == 3  # All tools in fixture are tier 1


def test_tool_wrapper_execution(registry_file):
    """Test tool wrapper execution with handler."""
    toolbox = MCPToolbox(registry_path=registry_file, enable_audit=False)
    toolbox.load_tools()
    
    # Register a mock handler
    def mock_handler(inputs, context):
        return {"result": "success", "input_echo": inputs.get("test")}
    
    toolbox.register_handler("mcp.github", mock_handler)
    
    # Execute the tool
    result = toolbox.execute_tool("mcp.github", {"test": "value"})
    assert result["result"] == "success"
    assert result["input_echo"] == "value"


def test_tool_wrapper_without_handler(registry_file):
    """Test tool wrapper execution without registered handler."""
    toolbox = MCPToolbox(registry_path=registry_file, enable_audit=False)
    toolbox.load_tools()
    
    # Execute tool without handler should return not_implemented
    result = toolbox.execute_tool("mcp.github", {"test": "value"})
    assert result["status"] == "not_implemented"
    assert result["tool_id"] == "mcp.github"


def test_tool_execution_with_audit(registry_file, audit_log_path):
    """Test tool execution with audit logging."""
    audit_logger = MCPAuditLogger(log_path=audit_log_path)
    toolbox = MCPToolbox(
        registry_path=registry_file,
        audit_logger=audit_logger,
    )
    toolbox.load_tools()
    
    # Register a handler
    def mock_handler(inputs, context):
        return {"status": "ok"}
    
    toolbox.register_handler("mcp.github", mock_handler)
    
    # Execute tool
    result = toolbox.execute_tool("mcp.github", {"repo": "test"})
    assert result["status"] == "ok"
    
    # Flush audit log
    audit_logger.flush()
    
    # Check audit log was written
    assert audit_log_path.exists()
    audit_content = audit_log_path.read_text()
    assert "mcp.github" in audit_content
    assert "tool_execution" in audit_content


def test_tool_execution_error_handling(registry_file):
    """Test error handling during tool execution."""
    toolbox = MCPToolbox(registry_path=registry_file, enable_audit=False)
    toolbox.load_tools()
    
    # Register a failing handler
    def failing_handler(inputs, context):
        raise ValueError("Test error")
    
    toolbox.register_handler("mcp.github", failing_handler)
    
    # Execution should raise ToolExecutionError
    with pytest.raises(ToolExecutionError) as exc_info:
        toolbox.execute_tool("mcp.github", {})
    
    assert "Test error" in str(exc_info.value)
    assert "mcp.github" in str(exc_info.value)


def test_unregistered_tool_execution(registry_file):
    """Test that executing unregistered tool raises error."""
    toolbox = MCPToolbox(registry_path=registry_file, enable_audit=False)
    toolbox.load_tools()
    
    with pytest.raises(MCPToolboxError) as exc_info:
        toolbox.execute_tool("mcp.nonexistent", {})
    
    assert "not available" in str(exc_info.value)


def test_sandbox_guard():
    """Test sandbox guard validation."""
    # Valid sandbox
    manifest = MCPToolManifest(
        tool_id="test",
        tier=1,
        enabled=True,
        protocol="mcp",
        ref="docker://test",
        sandbox="py-slim",
        scopes=[],
        env={},
        mounts=[],
        budget_policy="warn",
    )
    
    # Should not raise
    sandbox_guard(manifest, {}, {})
    
    # Invalid sandbox
    manifest_invalid = MCPToolManifest(
        tool_id="test",
        tier=1,
        enabled=True,
        protocol="mcp",
        ref="docker://test",
        sandbox="invalid-sandbox",
        scopes=[],
        env={},
        mounts=[],
        budget_policy="warn",
    )
    
    with pytest.raises(GuardCheckError):
        sandbox_guard(manifest_invalid, {}, {})


def test_tier_guard():
    """Test tier guard validation."""
    manifest = MCPToolManifest(
        tool_id="test",
        tier=2,
        enabled=True,
        protocol="mcp",
        ref="docker://test",
        sandbox="py-slim",
        scopes=[],
        env={},
        mounts=[],
        budget_policy="warn",
    )
    
    # Should pass if no tier restriction
    tier_guard(manifest, {}, {})
    
    # Should pass if tier is allowed
    tier_guard(manifest, {}, {"allowed_tiers": [1, 2]})
    
    # Should fail if tier not allowed
    with pytest.raises(GuardCheckError):
        tier_guard(manifest, {}, {"allowed_tiers": [1]})


def test_budget_guard():
    """Test budget guard validation."""
    manifest = MCPToolManifest(
        tool_id="test",
        tier=1,
        enabled=True,
        protocol="mcp",
        ref="docker://test",
        sandbox="py-slim",
        scopes=[],
        env={},
        mounts=[],
        budget_policy="block",
    )
    
    # Should pass if under budget
    budget_guard(manifest, {}, {"total_cost": 50, "budget_ceiling": 100})
    
    # Should fail if over budget with block policy
    with pytest.raises(GuardCheckError):
        budget_guard(manifest, {}, {"total_cost": 150, "budget_ceiling": 100})
    
    # Should warn but not fail with warn policy
    manifest.budget_policy = "warn"
    budget_guard(manifest, {}, {"total_cost": 150, "budget_ceiling": 100})


def test_add_global_guard(registry_file):
    """Test adding global guards to toolbox."""
    toolbox = MCPToolbox(registry_path=registry_file, enable_audit=False)
    toolbox.load_tools()
    
    # Add a custom guard
    guard_called = []
    
    def custom_guard(manifest, inputs, context):
        guard_called.append(manifest.id)
        if "forbidden" in inputs:
            raise GuardCheckError("Forbidden input detected")
    
    toolbox.add_guard(custom_guard)
    
    # Register handler
    def mock_handler(inputs, context):
        return {"status": "ok"}
    
    toolbox.register_handler("mcp.github", mock_handler)
    
    # Execute with valid input
    result = toolbox.execute_tool("mcp.github", {"test": "value"})
    assert result["status"] == "ok"
    assert "mcp.github" in guard_called
    
    # Execute with forbidden input
    with pytest.raises(GuardCheckError):
        toolbox.execute_tool("mcp.github", {"forbidden": "value"})


def test_get_tool_manifest(registry_file):
    """Test getting tool manifest."""
    toolbox = MCPToolbox(registry_path=registry_file, enable_audit=False)
    toolbox.load_tools()
    
    manifest = toolbox.get_tool_manifest("mcp.github")
    assert manifest.id == "mcp.github"
    assert manifest.tier == 1
    assert manifest.sandbox == "py-slim"
    assert "vcs" in manifest.scopes


def test_get_tools_by_tier(registry_file):
    """Test filtering tools by tier."""
    toolbox = MCPToolbox(registry_path=registry_file, enable_audit=False)
    toolbox.load_tools()
    
    tier1_tools = toolbox.get_tools_by_tier(1)
    assert len(tier1_tools) == 3
    assert all(tool in tier1_tools for tool in ["mcp.github", "mcp.fs", "mcp.browser"])


def test_get_tools_by_scope(registry_file):
    """Test filtering tools by scope."""
    toolbox = MCPToolbox(registry_path=registry_file, enable_audit=False)
    toolbox.load_tools()
    
    vcs_tools = toolbox.get_tools_by_scope("vcs")
    assert len(vcs_tools) == 1
    assert "mcp.github" in vcs_tools
    
    fs_tools = toolbox.get_tools_by_scope("fs")
    assert len(fs_tools) == 1
    assert "mcp.fs" in fs_tools
    
    web_tools = toolbox.get_tools_by_scope("web")
    assert len(web_tools) == 1
    assert "mcp.browser" in web_tools


def test_create_toolbox_convenience(registry_file):
    """Test the convenience function for creating toolbox."""
    toolbox = create_toolbox(
        registry_path=registry_file,
        allowed_tiers=[1],
        enable_audit=False,
        enable_guards=True,
    )
    
    # Should be loaded and have guards
    assert toolbox._loaded
    assert len(toolbox._guards) > 0
    assert len(toolbox.list_tools()) > 0


def test_toolbox_close(registry_file, audit_log_path):
    """Test toolbox cleanup."""
    audit_logger = MCPAuditLogger(log_path=audit_log_path, auto_flush=False)
    toolbox = MCPToolbox(
        registry_path=registry_file,
        audit_logger=audit_logger,
    )
    toolbox.load_tools()
    
    # Execute a tool
    toolbox.execute_tool("mcp.github", {})
    
    # Close should flush audit log
    toolbox.close()
    
    # Check audit log was written
    assert audit_log_path.exists()


def test_lazy_loading(registry_file):
    """Test that toolbox loads lazily."""
    toolbox = MCPToolbox(registry_path=registry_file, enable_audit=False)
    
    assert not toolbox._loaded
    
    # First access should trigger load
    tools = toolbox.list_tools()
    assert toolbox._loaded
    assert len(tools) > 0


def test_register_handler_for_unloaded_tool(registry_file):
    """Test registering handler triggers loading."""
    toolbox = MCPToolbox(registry_path=registry_file, enable_audit=False)
    
    assert not toolbox._loaded
    
    # Registering handler should trigger load
    def mock_handler(inputs, context):
        return {"status": "ok"}
    
    toolbox.register_handler("mcp.github", mock_handler)
    
    assert toolbox._loaded


def test_register_handler_for_invalid_tool(registry_file):
    """Test registering handler for invalid tool."""
    toolbox = MCPToolbox(registry_path=registry_file, enable_audit=False)
    toolbox.load_tools()
    
    def mock_handler(inputs, context):
        return {}
    
    with pytest.raises(MCPToolboxError):
        toolbox.register_handler("mcp.nonexistent", mock_handler)


def test_execution_context_propagation(registry_file):
    """Test that execution context is propagated to handler."""
    toolbox = MCPToolbox(registry_path=registry_file, enable_audit=False)
    toolbox.load_tools()
    
    received_context = {}
    
    def mock_handler(inputs, context):
        received_context.update(context)
        return {"status": "ok"}
    
    toolbox.register_handler("mcp.github", mock_handler)
    
    # Execute with context
    toolbox.execute_tool(
        "mcp.github",
        {"test": "value"},
        context={"trace_id": "test-123", "user_id": "user-456"},
    )
    
    assert received_context["trace_id"] == "test-123"
    assert received_context["user_id"] == "user-456"


def test_tool_wrapper_guard_execution_order(registry_file):
    """Test that guards are executed before handler."""
    toolbox = MCPToolbox(registry_path=registry_file, enable_audit=False)
    toolbox.load_tools()
    
    execution_order = []
    
    def custom_guard(manifest, inputs, context):
        execution_order.append("guard")
    
    def mock_handler(inputs, context):
        execution_order.append("handler")
        return {"status": "ok"}
    
    toolbox.add_guard(custom_guard)
    toolbox.register_handler("mcp.github", mock_handler)
    
    toolbox.execute_tool("mcp.github", {})
    
    assert execution_order == ["guard", "handler"]


def test_multiple_guards(registry_file):
    """Test multiple guards are executed in order."""
    toolbox = MCPToolbox(registry_path=registry_file, enable_audit=False)
    toolbox.load_tools()
    
    guard_order = []
    
    def guard1(manifest, inputs, context):
        guard_order.append(1)
    
    def guard2(manifest, inputs, context):
        guard_order.append(2)
    
    def guard3(manifest, inputs, context):
        guard_order.append(3)
    
    toolbox.add_guard(guard1)
    toolbox.add_guard(guard2)
    toolbox.add_guard(guard3)
    
    def mock_handler(inputs, context):
        return {"status": "ok"}
    
    toolbox.register_handler("mcp.github", mock_handler)
    
    toolbox.execute_tool("mcp.github", {})
    
    assert guard_order == [1, 2, 3]


def test_guard_failure_prevents_execution(registry_file):
    """Test that guard failure prevents handler execution."""
    toolbox = MCPToolbox(registry_path=registry_file, enable_audit=False)
    toolbox.load_tools()
    
    handler_called = []
    
    def failing_guard(manifest, inputs, context):
        raise GuardCheckError("Guard failed")
    
    def mock_handler(inputs, context):
        handler_called.append(True)
        return {"status": "ok"}
    
    toolbox.add_guard(failing_guard)
    toolbox.register_handler("mcp.github", mock_handler)
    
    with pytest.raises(GuardCheckError):
        toolbox.execute_tool("mcp.github", {})
    
    # Handler should not have been called
    assert len(handler_called) == 0
