"""Tests for MCP executor integration."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cuga.agents.executor import Executor
from cuga.agents.registry import ToolRegistry
from cuga.agents.executor_mcp import (
    MCPExecutorMixin,
    MCPToolRegistryAdapter,
    create_mcp_enhanced_registry,
)
from cuga.orchestrator.protocol import ExecutionContext
from cuga.agents.planner import PlanStep


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
  - id: mcp.test_tool
    ref: docker://test
    scopes: [test]
    mounts: []
  
  - id: mcp.another_tool
    ref: docker://another
    scopes: [test]
    mounts: []
"""


@pytest.fixture
def registry_file(sample_registry_yaml, tmp_path):
    """Create a temporary registry file."""
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(sample_registry_yaml)
    return registry_path


def test_mcp_tool_registry_adapter_initialization(registry_file):
    """Test adapter initialization."""
    adapter = MCPToolRegistryAdapter(
        registry_path=registry_file,
        allowed_tiers=[1],
        enable_audit=False,
    )
    
    # Should have loaded tools from registry
    assert adapter.mcp_toolbox._loaded
    assert len(adapter.mcp_toolbox.list_tools()) == 2


def test_register_mcp_tools(registry_file):
    """Test registering MCP tools into ToolRegistry."""
    adapter = MCPToolRegistryAdapter(
        registry_path=registry_file,
        enable_audit=False,
    )
    
    tool_registry = ToolRegistry()
    profile = "test_profile"
    
    # Register all MCP tools
    adapter.register_mcp_tools(tool_registry, profile)
    
    # Verify tools were registered
    assert "mcp.test_tool" in tool_registry._tools[profile]
    assert "mcp.another_tool" in tool_registry._tools[profile]


def test_register_specific_mcp_tools(registry_file):
    """Test registering specific MCP tools."""
    adapter = MCPToolRegistryAdapter(
        registry_path=registry_file,
        enable_audit=False,
    )
    
    tool_registry = ToolRegistry()
    profile = "test_profile"
    
    # Register only one tool
    adapter.register_mcp_tools(tool_registry, profile, ["mcp.test_tool"])
    
    # Verify only the specified tool was registered
    assert "mcp.test_tool" in tool_registry._tools[profile]
    assert "mcp.another_tool" not in tool_registry._tools.get(profile, {})


def test_register_mcp_tools_by_tier(registry_file):
    """Test registering tools by tier."""
    adapter = MCPToolRegistryAdapter(
        registry_path=registry_file,
        enable_audit=False,
    )
    
    tool_registry = ToolRegistry()
    profile = "test_profile"
    
    # Register tier 1 tools
    adapter.register_mcp_tools_by_tier(tool_registry, profile, 1)
    
    # All fixture tools are tier 1
    assert "mcp.test_tool" in tool_registry._tools[profile]
    assert "mcp.another_tool" in tool_registry._tools[profile]


def test_register_mcp_tools_by_scope(registry_file):
    """Test registering tools by scope."""
    adapter = MCPToolRegistryAdapter(
        registry_path=registry_file,
        enable_audit=False,
    )
    
    tool_registry = ToolRegistry()
    profile = "test_profile"
    
    # Register tools with 'test' scope
    adapter.register_mcp_tools_by_scope(tool_registry, profile, "test")
    
    # Both tools have 'test' scope
    assert "mcp.test_tool" in tool_registry._tools[profile]
    assert "mcp.another_tool" in tool_registry._tools[profile]


def test_tool_handler_execution(registry_file):
    """Test that registered MCP tool handlers can be executed."""
    adapter = MCPToolRegistryAdapter(
        registry_path=registry_file,
        enable_audit=False,
    )
    
    # Register a mock handler for the MCP tool
    def mock_handler(inputs, context):
        return {"status": "ok", "input_echo": inputs.get("test")}
    
    adapter.mcp_toolbox.register_handler("mcp.test_tool", mock_handler)
    
    tool_registry = ToolRegistry()
    profile = "test_profile"
    
    # Register MCP tools
    adapter.register_mcp_tools(tool_registry, profile)
    
    # Get the registered tool entry
    tool_entry = tool_registry.resolve(profile, "mcp.test_tool")
    handler = tool_entry["handler"]
    
    # Execute the handler
    result = handler({"test": "value"})
    
    assert result["status"] == "ok"
    assert result["input_echo"] == "value"


def test_create_mcp_enhanced_registry(registry_file):
    """Test convenience function for creating MCP-enhanced registry."""
    registry = create_mcp_enhanced_registry(
        profile="test_profile",
        registry_path=registry_file,
        allowed_tiers=[1],
        enable_audit=False,
        include_all_tools=True,
    )
    
    # Should have MCP tools registered
    assert "mcp.test_tool" in registry._tools["test_profile"]
    assert "mcp.another_tool" in registry._tools["test_profile"]


def test_executor_with_mcp_tools(registry_file):
    """Test executor can execute MCP tools."""
    # Create registry and register MCP tools
    adapter = MCPToolRegistryAdapter(
        registry_path=registry_file,
        enable_audit=False,
    )
    
    # Register a mock handler
    def mock_handler(inputs, context):
        return {"status": "success", "data": inputs.get("data")}
    
    adapter.mcp_toolbox.register_handler("mcp.test_tool", mock_handler)
    
    tool_registry = ToolRegistry()
    profile = "test_profile"
    adapter.register_mcp_tools(tool_registry, profile)
    
    # Create executor and execute a plan
    executor = Executor()
    
    plan = [
        PlanStep(
            name="step1",
            tool="mcp.test_tool",
            input={"data": "test_value"},
        )
    ]
    
    context = ExecutionContext(
        trace_id="test-trace",
        profile=profile,
    )
    
    result = executor.execute_plan(plan, tool_registry, context)
    
    # Verify execution
    assert result.output["status"] == "success"
    assert result.output["data"] == "test_value"
    assert len(result.steps) == 1


def test_mcp_executor_mixin():
    """Test MCPExecutorMixin functionality."""
    
    class TestExecutor(MCPExecutorMixin, Executor):
        pass
    
    # Create test registry YAML
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("""
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
  - id: mcp.mixin_test
    ref: docker://test
    scopes: [test]
    mounts: []
""")
        registry_path = Path(f.name)
    
    try:
        # Create executor with mixin
        executor = TestExecutor()
        
        tool_registry = ToolRegistry()
        profile = "test_profile"
        
        # Load MCP tools via mixin
        executor.load_mcp_tools(
            registry=tool_registry,
            profile=profile,
            registry_path=registry_path,
            allowed_tiers=[1],
        )
        
        # Verify tools were loaded
        assert "mcp.mixin_test" in tool_registry._tools[profile]
    finally:
        registry_path.unlink()


def test_context_conversion(registry_file):
    """Test that execution context is properly converted for MCP tools."""
    adapter = MCPToolRegistryAdapter(
        registry_path=registry_file,
        enable_audit=False,
    )
    
    received_context = {}
    
    def mock_handler(inputs, context):
        received_context.update(context)
        return {"status": "ok"}
    
    adapter.mcp_toolbox.register_handler("mcp.test_tool", mock_handler)
    
    tool_registry = ToolRegistry()
    profile = "test_profile"
    adapter.register_mcp_tools(tool_registry, profile)
    
    # Execute with ExecutionContext
    executor = Executor()
    
    plan = [
        PlanStep(
            name="step1",
            tool="mcp.test_tool",
            input={},
        )
    ]
    
    context = ExecutionContext(
        trace_id="test-trace-123",
        profile=profile,
    )
    
    executor.execute_plan(plan, tool_registry, context)
    
    # Verify context was converted properly
    assert received_context.get("profile") == profile
    assert received_context.get("trace_id") == "test-trace-123"


def test_deterministic_execution(registry_file):
    """Test that MCP tool execution is deterministic."""
    adapter = MCPToolRegistryAdapter(
        registry_path=registry_file,
        enable_audit=False,
    )
    
    call_count = []
    
    def deterministic_handler(inputs, context):
        call_count.append(1)
        return {"result": len(call_count), "input": inputs.get("value")}
    
    adapter.mcp_toolbox.register_handler("mcp.test_tool", deterministic_handler)
    
    tool_registry = ToolRegistry()
    profile = "test_profile"
    adapter.register_mcp_tools(tool_registry, profile)
    
    executor = Executor()
    
    # Execute same plan multiple times
    results = []
    for i in range(3):
        call_count.clear()
        plan = [
            PlanStep(
                name="step1",
                tool="mcp.test_tool",
                input={"value": i},
            )
        ]
        
        context = ExecutionContext(
            trace_id=f"trace-{i}",
            profile=profile,
        )
        
        result = executor.execute_plan(plan, tool_registry, context)
        results.append(result.output)
    
    # Verify each execution was independent and deterministic
    assert results[0]["input"] == 0
    assert results[1]["input"] == 1
    assert results[2]["input"] == 2


def test_granite_workflow_compatibility(registry_file):
    """Test that MCP integration doesn't break existing Granite workflows."""
    # Create a registry with both regular and MCP tools
    tool_registry = ToolRegistry()
    profile = "test_profile"
    
    # Register a regular (non-MCP) tool
    def regular_tool(inputs, config=None, context=None):
        return {"type": "regular", "data": inputs.get("data")}
    
    tool_registry.register(
        profile=profile,
        name="regular_tool",
        handler=regular_tool,
        cost=1.0,
        latency=1.0,
    )
    
    # Register MCP tools
    adapter = MCPToolRegistryAdapter(
        registry_path=registry_file,
        enable_audit=False,
    )
    
    def mcp_tool(inputs, context):
        return {"type": "mcp", "data": inputs.get("data")}
    
    adapter.mcp_toolbox.register_handler("mcp.test_tool", mcp_tool)
    adapter.register_mcp_tools(tool_registry, profile)
    
    # Execute a plan with both tool types
    executor = Executor()
    
    plan = [
        PlanStep(
            name="step1",
            tool="regular_tool",
            input={"data": "regular_data"},
        ),
        PlanStep(
            name="step2",
            tool="mcp.test_tool",
            input={"data": "mcp_data"},
        ),
    ]
    
    context = ExecutionContext(
        trace_id="compatibility-test",
        profile=profile,
    )
    
    result = executor.execute_plan(plan, tool_registry, context)
    
    # Verify both tools executed correctly
    assert len(result.steps) == 2
    assert result.steps[0]["result"]["type"] == "regular"
    assert result.steps[0]["result"]["data"] == "regular_data"
    assert result.steps[1]["result"]["type"] == "mcp"
    assert result.steps[1]["result"]["data"] == "mcp_data"
