"""Tests for Executor integration with MCP toolbox."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict
from unittest.mock import Mock, patch

import pytest

from cuga.agents.executor import Executor, ExecutionResult
from cuga.agents.planner import PlanStep
from cuga.agents.policy import PolicyEnforcer
from cuga.agents.registry import ToolRegistry
from cuga.orchestrator.protocol import ExecutionContext
from cuga.tools.mcp_toolbox import MCPToolbox


@pytest.fixture
def sample_registry():
    """Create a sample tool registry for testing."""
    registry = ToolRegistry()

    def mock_tool_handler(input: Dict[str, Any], config: Dict[str, Any], context: Any) -> Dict[str, Any]:
        return {"result": "standard_tool", "input": input}

    registry.register(
        profile="default",
        name="standard.tool",
        handler=mock_tool_handler,
        cost=1.0,
        latency=0.5,
        description="Standard tool"
    )

    return registry


@pytest.fixture
def sample_context():
    """Create a sample execution context."""
    return ExecutionContext(
        trace_id="test_trace",
        profile="default",
        metadata={}
    )


@pytest.fixture
def sample_plan():
    """Create a sample execution plan."""
    return [
        PlanStep(name="step1", tool="standard.tool", input={"data": "test"})
    ]


@pytest.fixture
def mcp_registry_file(tmp_path):
    """Create a temporary MCP registry file."""
    import yaml
    
    registry_path = tmp_path / "mcp_registry.yaml"
    with open(registry_path, "w") as f:
        yaml.safe_dump({
            "version": "v1",
            "entries": [
                {
                    "id": "mcp.github",
                    "tier": 1,
                    "enabled": True,
                    "ref": "docker://github",
                    "scopes": ["vcs"],
                },
                {
                    "id": "mcp.crypto",
                    "tier": 2,
                    "enabled": True,
                    "ref": "docker://crypto",
                    "scopes": ["finance"],
                },
            ],
        }, f)
    
    return registry_path


class TestExecutorWithoutMCP:
    """Test standard executor behavior without MCP integration."""

    def test_executor_creation(self):
        """Test creating a standard executor."""
        executor = Executor()
        assert executor.policy_enforcer is None
        assert executor.enable_mcp is False
        assert executor.mcp_toolbox is None

    def test_execute_standard_tool(self, sample_registry, sample_context, sample_plan):
        """Test executing a standard tool through the registry."""
        executor = Executor()
        result = executor.execute_plan(sample_plan, sample_registry, sample_context)

        assert isinstance(result, ExecutionResult)
        assert len(result.steps) == 1
        assert result.steps[0]["tool"] == "standard.tool"
        assert result.steps[0]["result"]["result"] == "standard_tool"
        assert result.output == result.steps[0]["result"]

    def test_execute_with_policy_enforcer(self, sample_registry, sample_context, sample_plan):
        """Test executing with policy enforcement."""
        policy_enforcer = PolicyEnforcer()
        executor = Executor(policy_enforcer=policy_enforcer)
        
        result = executor.execute_plan(sample_plan, sample_registry, sample_context)
        
        assert len(result.steps) == 1
        assert result.output is not None


class TestExecutorWithMCP:
    """Test executor with MCP integration enabled."""

    def test_executor_creation_with_mcp(self, mcp_registry_file):
        """Test creating an executor with MCP enabled."""
        executor = Executor(
            enable_mcp=True,
            mcp_registry_path=mcp_registry_file,
            mcp_allowed_tiers=[1, 2]
        )

        assert executor.enable_mcp is True
        assert executor.mcp_toolbox is not None
        assert isinstance(executor.mcp_toolbox, MCPToolbox)

    def test_executor_with_provided_toolbox(self, mcp_registry_file):
        """Test executor with pre-configured MCP toolbox."""
        from cuga.tools.mcp_toolbox import create_mcp_toolbox
        
        toolbox = create_mcp_toolbox(
            allowed_tiers=[1],
            registry_path=mcp_registry_file
        )
        
        executor = Executor(enable_mcp=True, mcp_toolbox=toolbox)
        
        assert executor.mcp_toolbox is toolbox

    def test_execute_mcp_tool(self, sample_registry, sample_context, mcp_registry_file):
        """Test executing an MCP tool."""
        executor = Executor(
            enable_mcp=True,
            mcp_registry_path=mcp_registry_file,
            mcp_allowed_tiers=[1]
        )

        # Create a plan with an MCP tool
        plan = [
            PlanStep(name="mcp_step", tool="mcp.github", input={"repo": "test/repo"})
        ]

        result = executor.execute_plan(plan, sample_registry, sample_context)

        assert len(result.steps) == 1
        assert result.steps[0]["tool"] == "mcp.github"
        # Mock handler returns tool ID
        assert result.steps[0]["result"]["tool"] == "mcp.github"

    def test_execute_mixed_tools(self, sample_registry, sample_context, mcp_registry_file):
        """Test executing both standard and MCP tools in the same plan."""
        executor = Executor(
            enable_mcp=True,
            mcp_registry_path=mcp_registry_file,
            mcp_allowed_tiers=[1]
        )

        # Mixed plan
        plan = [
            PlanStep(name="step1", tool="standard.tool", input={"data": "test"}),
            PlanStep(name="step2", tool="mcp.github", input={"repo": "test"}),
        ]

        result = executor.execute_plan(plan, sample_registry, sample_context)

        assert len(result.steps) == 2
        assert result.steps[0]["tool"] == "standard.tool"
        assert result.steps[0]["result"]["result"] == "standard_tool"
        assert result.steps[1]["tool"] == "mcp.github"
        assert result.steps[1]["result"]["tool"] == "mcp.github"

    def test_mcp_tool_not_found(self, sample_registry, sample_context, mcp_registry_file):
        """Test handling of MCP tool not found."""
        executor = Executor(
            enable_mcp=True,
            mcp_registry_path=mcp_registry_file,
            mcp_allowed_tiers=[1]
        )

        # Try to execute an MCP tool that doesn't exist
        plan = [
            PlanStep(name="step1", tool="mcp.nonexistent", input={})
        ]

        result = executor.execute_plan(plan, sample_registry, sample_context)

        assert len(result.steps) == 1
        assert result.steps[0]["result"]["status"] == "failed"
        assert result.steps[0]["result"]["reason"] == "mcp_tool_not_found"

    def test_mcp_tool_tier_filtering(self, sample_registry, sample_context, mcp_registry_file):
        """Test that tier filtering works correctly."""
        # Only allow tier 1
        executor = Executor(
            enable_mcp=True,
            mcp_registry_path=mcp_registry_file,
            mcp_allowed_tiers=[1]
        )

        # mcp.crypto is tier 2, so it shouldn't be available
        plan = [
            PlanStep(name="step1", tool="mcp.crypto", input={})
        ]

        result = executor.execute_plan(plan, sample_registry, sample_context)

        assert result.steps[0]["result"]["status"] == "failed"
        assert result.steps[0]["result"]["reason"] == "mcp_tool_not_found"

    def test_deterministic_execution_order(self, sample_registry, sample_context, mcp_registry_file):
        """Test that execution order is deterministic."""
        executor = Executor(
            enable_mcp=True,
            mcp_registry_path=mcp_registry_file,
            mcp_allowed_tiers=[1]
        )

        plan = [
            PlanStep(name="a", tool="standard.tool", input={"id": 1}),
            PlanStep(name="b", tool="mcp.github", input={"id": 2}),
            PlanStep(name="c", tool="standard.tool", input={"id": 3}),
        ]

        # Execute multiple times
        result1 = executor.execute_plan(plan, sample_registry, sample_context)
        result2 = executor.execute_plan(plan, sample_registry, sample_context)

        # Results should be in the same order
        assert len(result1.steps) == len(result2.steps) == 3
        assert [s["step"] for s in result1.steps] == [s["step"] for s in result2.steps]
        assert [s["tool"] for s in result1.steps] == [s["tool"] for s in result2.steps]


class TestExecutorAuditTrail:
    """Test audit trail functionality."""

    def test_audit_trail_captured(self, sample_registry, sample_context, sample_plan):
        """Test that audit trail is captured."""
        executor = Executor()
        result = executor.execute_plan(sample_plan, sample_registry, sample_context, trace=[])

        assert result.trace is not None
        assert len(result.trace) == 1
        assert result.trace[0]["event"] == "execute_step"
        assert result.trace[0]["tool"] == "standard.tool"
        assert result.trace[0]["status"] == "success"

    def test_mcp_audit_trail(self, sample_registry, sample_context, mcp_registry_file):
        """Test audit trail for MCP tools."""
        executor = Executor(
            enable_mcp=True,
            mcp_registry_path=mcp_registry_file,
            mcp_allowed_tiers=[1]
        )

        plan = [
            PlanStep(name="mcp_step", tool="mcp.github", input={"repo": "test"})
        ]

        result = executor.execute_plan(plan, sample_registry, sample_context, trace=[])

        assert result.trace is not None
        assert len(result.trace) == 1
        assert result.trace[0]["event"] == "execute_mcp_tool"
        assert result.trace[0]["tool"] == "mcp.github"


class TestExecutorErrorHandling:
    """Test error handling in executor."""

    def test_standard_tool_error(self, sample_registry, sample_context):
        """Test handling of standard tool errors."""
        # Register a failing tool
        def failing_handler(input: Dict[str, Any], config: Dict[str, Any], context: Any) -> Dict[str, Any]:
            raise ValueError("Test error")

        sample_registry.register(
            profile="default",
            name="failing.tool",
            handler=failing_handler
        )

        executor = Executor()
        plan = [
            PlanStep(name="step1", tool="failing.tool", input={})
        ]

        result = executor.execute_plan(plan, sample_registry, sample_context)

        assert result.steps[0]["result"]["status"] == "failed"
        assert result.steps[0]["result"]["reason"] == "handler_error"

    def test_mcp_guard_check_failure(self, sample_registry, sample_context, mcp_registry_file):
        """Test handling of MCP guard check failures."""
        # Create executor with MCP
        executor = Executor(
            enable_mcp=True,
            mcp_registry_path=mcp_registry_file,
            mcp_allowed_tiers=[1]
        )

        # Mock the guard to fail
        with patch.object(executor.mcp_toolbox.guard, 'evaluate') as mock_guard:
            from cuga.guards.orchestrator import GuardResult
            mock_guard.return_value = GuardResult(decision="fail", details={"reason": "test"})

            plan = [
                PlanStep(name="step1", tool="mcp.github", input={})
            ]

            result = executor.execute_plan(plan, sample_registry, sample_context)

            assert result.steps[0]["result"]["status"] == "failed"
            assert "guard_check_failed" in result.steps[0]["result"]["reason"]


class TestBackwardCompatibility:
    """Test backward compatibility with existing code."""

    def test_executor_without_mcp_params(self, sample_registry, sample_context, sample_plan):
        """Test that executor works without MCP-related parameters."""
        # Old-style executor creation should still work
        executor = Executor()
        result = executor.execute_plan(sample_plan, sample_registry, sample_context)

        assert result is not None
        assert len(result.steps) == 1

    def test_existing_registry_still_works(self, sample_registry, sample_context):
        """Test that existing registry-based tools still work."""
        executor = Executor()

        # Multiple standard tools
        plan = [
            PlanStep(name="step1", tool="standard.tool", input={"a": 1}),
            PlanStep(name="step2", tool="standard.tool", input={"b": 2}),
        ]

        result = executor.execute_plan(plan, sample_registry, sample_context)

        assert len(result.steps) == 2
        assert all(s["result"]["result"] == "standard_tool" for s in result.steps)
