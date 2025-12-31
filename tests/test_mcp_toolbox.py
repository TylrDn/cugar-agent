"""Tests for MCP toolbox with guard enforcement and audit logging."""

from pathlib import Path
from typing import Any, Dict
from unittest.mock import Mock, patch

import pytest

from cuga.observability.mcp_audit import MCPAuditLogger, MCPAuditRecord, normalize_output
from cuga.tools.mcp_registry import MCPToolEntry
from cuga.tools.mcp_toolbox import GuardedMCPTool, MCPToolbox, create_mcp_toolbox


@pytest.fixture
def temp_audit_file(tmp_path):
    """Create a temporary audit file for testing."""
    audit_file = tmp_path / "test_audit.jsonl"
    return audit_file


@pytest.fixture
def sample_tool_entry():
    """Create a sample tool entry for testing."""
    return MCPToolEntry(
        id="test.tool",
        tier=1,
        enabled=True,
        protocol="mcp",
        sandbox="py-slim",
        scopes=["read"],
        env={},
        mounts=[],
        ref="docker://test",
        constraints={"cost": 1.0, "latency": 0.5},
    )


@pytest.fixture
def mock_handler():
    """Create a mock tool handler."""

    def handler(input: Dict[str, Any]) -> Dict[str, Any]:
        return {"result": "success", "input": input}

    return handler


class TestMCPAuditRecord:
    """Test MCPAuditRecord."""

    def test_record_creation(self):
        """Test creating an audit record."""
        record = MCPAuditRecord(
            tool_id="test.tool",
            method="execute",
            input={"param": "value"},
            trace_id="trace123",
        )

        assert record.tool_id == "test.tool"
        assert record.method == "execute"
        assert record.input == {"param": "value"}
        assert record.trace_id == "trace123"
        assert record.status == "pending"

    def test_redact_sensitive_fields(self):
        """Test redaction of sensitive fields."""
        record = MCPAuditRecord(
            tool_id="test",
            input={
                "username": "alice",
                "password": "secret123",
                "api_token": "xyz",
                "data": "public",
            },
            output={"secret_key": "hidden", "result": "ok"},
            metadata={"GitHub_Token": "ghp_xxx"},
        )

        record.redact_sensitive_fields()

        assert record.input["username"] == "alice"
        assert record.input["password"] == "[REDACTED]"
        assert record.input["api_token"] == "[REDACTED]"
        assert record.input["data"] == "public"
        assert record.output["secret_key"] == "[REDACTED]"
        assert record.output["result"] == "ok"
        assert record.metadata["GitHub_Token"] == "[REDACTED]"

    def test_to_dict(self):
        """Test conversion to dictionary."""
        record = MCPAuditRecord(tool_id="test", method="execute")
        record_dict = record.to_dict()

        assert isinstance(record_dict, dict)
        assert record_dict["tool_id"] == "test"
        assert record_dict["method"] == "execute"
        assert "timestamp" in record_dict


class TestMCPAuditLogger:
    """Test MCPAuditLogger."""

    def test_logger_creation(self, temp_audit_file):
        """Test creating an audit logger."""
        logger = MCPAuditLogger(audit_file=temp_audit_file)
        assert logger.audit_file == temp_audit_file
        assert logger.redact_sensitive is True
        assert logger.auto_flush is True

    def test_log_invocation(self, temp_audit_file):
        """Test logging a tool invocation."""
        logger = MCPAuditLogger(audit_file=temp_audit_file)

        record = logger.log_invocation(
            tool_id="test.tool",
            method="execute",
            input={"param": "value"},
            trace_id="trace123",
            tier=1,
        )

        assert record.tool_id == "test.tool"
        assert record.method == "execute"
        assert record.trace_id == "trace123"
        assert record.tool_tier == 1

        # Verify written to file
        assert temp_audit_file.exists()

    def test_log_completion(self, temp_audit_file):
        """Test logging successful completion."""
        logger = MCPAuditLogger(audit_file=temp_audit_file)

        record = logger.log_invocation(
            tool_id="test.tool", method="execute", input={}, tier=1
        )

        logger.log_completion(
            record=record, output={"result": "ok"}, duration_ms=100.0, cost=1.0, latency=0.5
        )

        assert record.status == "success"
        assert record.output == {"result": "ok"}
        assert record.duration_ms == 100.0
        assert record.cost == 1.0
        assert record.latency == 0.5

    def test_log_error(self, temp_audit_file):
        """Test logging an error."""
        logger = MCPAuditLogger(audit_file=temp_audit_file)

        record = logger.log_invocation(
            tool_id="test.tool", method="execute", input={}, tier=1
        )

        logger.log_error(record=record, error="Test error", duration_ms=50.0)

        assert record.status == "error"
        assert record.error == "Test error"
        assert record.duration_ms == 50.0

    def test_read_all(self, temp_audit_file):
        """Test reading all audit records."""
        logger = MCPAuditLogger(audit_file=temp_audit_file, redact_sensitive=False)

        # Log multiple records
        for i in range(3):
            logger.log_invocation(
                tool_id=f"tool{i}", method="execute", input={"id": i}, tier=1
            )

        records = logger.read_all()
        assert len(records) == 3
        assert records[0].tool_id == "tool0"
        assert records[1].tool_id == "tool1"
        assert records[2].tool_id == "tool2"

    def test_get_statistics(self, temp_audit_file):
        """Test getting statistics from audit log."""
        logger = MCPAuditLogger(audit_file=temp_audit_file, redact_sensitive=False)

        # Log some records (each invocation + completion/error = 2 records)
        record1 = logger.log_invocation(tool_id="tool1", method="exec", input={}, tier=1)
        logger.log_completion(record1, output={}, duration_ms=100.0, cost=1.0)

        record2 = logger.log_invocation(tool_id="tool2", method="exec", input={}, tier=2)
        logger.log_error(record2, error="Failed", duration_ms=50.0)

        record3 = logger.log_invocation(tool_id="tool1", method="exec", input={}, tier=1)
        logger.log_completion(record3, output={}, duration_ms=150.0, cost=2.0)

        stats = logger.get_statistics()

        # We log both invocation and completion, so 6 total records
        assert stats["total_invocations"] == 6
        assert stats["successful"] == 2
        assert stats["failed"] == 1
        # 3 pending + 2 success + 1 failed = 6 total, success rate is 2/6
        assert stats["success_rate"] == pytest.approx(2 / 6)
        assert stats["total_cost"] == 3.0
        assert stats["total_duration_ms"] == 300.0
        assert stats["avg_duration_ms"] == 50.0  # 300 / 6
        # Each tool appears twice (invocation + completion)
        assert stats["tools"] == {"tool1": 4, "tool2": 2}
        assert stats["tiers"] == {1: 4, 2: 2}

    def test_sensitive_redaction_in_log(self, temp_audit_file):
        """Test that sensitive fields are redacted when logging."""
        logger = MCPAuditLogger(audit_file=temp_audit_file, redact_sensitive=True)

        logger.log_invocation(
            tool_id="test",
            method="exec",
            input={"password": "secret", "data": "public"},
            tier=1,
        )

        records = logger.read_all()
        assert len(records) == 1
        assert records[0].input["password"] == "[REDACTED]"
        assert records[0].input["data"] == "public"


class TestNormalizeOutput:
    """Test normalize_output function."""

    def test_normalize_dict(self):
        """Test normalizing dictionaries."""
        output = {"z": 3, "a": 1, "timestamp": "2024-01-01", "b": 2}
        normalized = normalize_output(output)

        # Should be sorted and timestamp removed
        assert list(normalized.keys()) == ["a", "b", "z"]
        assert "timestamp" not in normalized

    def test_normalize_nested_dict(self):
        """Test normalizing nested dictionaries."""
        output = {"data": {"z": 1, "a": 2, "created_at": "2024"}, "timestamp": "2024"}

        normalized = normalize_output(output)

        assert "timestamp" not in normalized
        assert "created_at" not in normalized["data"]
        assert list(normalized["data"].keys()) == ["a", "z"]

    def test_normalize_list(self):
        """Test normalizing lists."""
        output = [{"b": 2, "a": 1}, {"d": 4, "c": 3, "time": "2024"}]
        normalized = normalize_output(output)

        assert list(normalized[0].keys()) == ["a", "b"]
        assert list(normalized[1].keys()) == ["c", "d"]


class TestGuardedMCPTool:
    """Test GuardedMCPTool."""

    def test_tool_creation(self, sample_tool_entry, mock_handler, temp_audit_file):
        """Test creating a guarded tool."""
        from cuga.guards.tool_guard import ToolGuard

        guard = ToolGuard()
        audit_logger = MCPAuditLogger(audit_file=temp_audit_file)

        tool = GuardedMCPTool(
            tool_entry=sample_tool_entry,
            handler=mock_handler,
            guard=guard,
            audit_logger=audit_logger,
        )

        assert tool.tool_entry == sample_tool_entry
        assert tool.handler == mock_handler
        assert tool.guard == guard
        assert tool.audit_logger == audit_logger

    def test_tool_execution(self, sample_tool_entry, mock_handler, temp_audit_file):
        """Test executing a guarded tool."""
        from cuga.guards.tool_guard import ToolGuard

        guard = ToolGuard()
        audit_logger = MCPAuditLogger(audit_file=temp_audit_file, redact_sensitive=False)

        tool = GuardedMCPTool(
            tool_entry=sample_tool_entry,
            handler=mock_handler,
            guard=guard,
            audit_logger=audit_logger,
        )

        result = tool({"test": "data"}, {"trace_id": "trace123", "profile": "default"})

        assert result == {"result": "success", "input": {"test": "data"}}

        # Verify audit log
        records = audit_logger.read_all()
        assert len(records) == 2  # invocation + completion
        assert records[0].tool_id == "test.tool"
        assert records[0].status == "pending"
        assert records[1].status == "success"

    def test_tool_execution_error(self, sample_tool_entry, temp_audit_file):
        """Test tool execution with error."""
        from cuga.guards.tool_guard import ToolGuard

        def failing_handler(input: Dict[str, Any]) -> Dict[str, Any]:
            raise ValueError("Test error")

        guard = ToolGuard()
        audit_logger = MCPAuditLogger(audit_file=temp_audit_file)

        tool = GuardedMCPTool(
            tool_entry=sample_tool_entry,
            handler=failing_handler,
            guard=guard,
            audit_logger=audit_logger,
        )

        with pytest.raises(ValueError, match="Test error"):
            tool({}, {})

        # Verify error logged
        records = audit_logger.read_all()
        assert len(records) == 2
        assert records[1].status == "error"
        assert records[1].error == "Test error"


class TestMCPToolbox:
    """Test MCPToolbox."""

    def test_toolbox_creation(self, tmp_path):
        """Test creating an MCP toolbox."""
        registry_file = tmp_path / "registry.yaml"
        audit_file = tmp_path / "audit.jsonl"

        # Create minimal registry
        import yaml

        with open(registry_file, "w") as f:
            yaml.safe_dump(
                {
                    "version": "v1",
                    "entries": [
                        {"id": "test.tool1", "tier": 1, "enabled": True},
                        {"id": "test.tool2", "tier": 2, "enabled": True},
                    ],
                },
                f,
            )

        toolbox = MCPToolbox(
            registry_path=registry_file,
            audit_file=audit_file,
            allowed_tiers=[1],
            deny_by_default=False,
        )

        assert toolbox.allowed_tiers == [1]
        assert toolbox.registry_loader.deny_by_default is False

    def test_load_tools_deterministic_ordering(self, tmp_path):
        """Test that load_tools returns tools in deterministic order."""
        registry_file = tmp_path / "registry.yaml"
        import yaml

        # Create tools in non-alphabetical order
        with open(registry_file, "w") as f:
            yaml.safe_dump(
                {
                    "version": "v1",
                    "entries": [
                        {"id": "zebra", "tier": 1, "enabled": True},
                        {"id": "alpha", "tier": 1, "enabled": True},
                        {"id": "beta", "tier": 1, "enabled": True},
                    ],
                },
                f,
            )

        toolbox = MCPToolbox(registry_path=registry_file, allowed_tiers=[1])
        tools = toolbox.load_tools()

        ids = list(tools.keys())
        assert ids == ["alpha", "beta", "zebra"]

    def test_load_tools_tier_filtering(self, tmp_path):
        """Test that load_tools filters by allowed tiers."""
        registry_file = tmp_path / "registry.yaml"
        import yaml

        with open(registry_file, "w") as f:
            yaml.safe_dump(
                {
                    "version": "v1",
                    "entries": [
                        {"id": "tier1", "tier": 1, "enabled": True},
                        {"id": "tier2", "tier": 2, "enabled": True},
                        {"id": "tier3", "tier": 3, "enabled": True},
                    ],
                },
                f,
            )

        # Load only tier 1
        toolbox = MCPToolbox(registry_path=registry_file, allowed_tiers=[1])
        tools = toolbox.load_tools()
        assert len(tools) == 1
        assert "tier1" in tools

        # Load tiers 1 and 2
        toolbox = MCPToolbox(registry_path=registry_file, allowed_tiers=[1, 2])
        tools = toolbox.load_tools()
        assert len(tools) == 2
        assert "tier1" in tools
        assert "tier2" in tools

    def test_list_tool_ids(self, tmp_path):
        """Test listing tool IDs."""
        registry_file = tmp_path / "registry.yaml"
        import yaml

        with open(registry_file, "w") as f:
            yaml.safe_dump(
                {
                    "version": "v1",
                    "entries": [
                        {"id": "c", "tier": 1, "enabled": True},
                        {"id": "a", "tier": 1, "enabled": True},
                        {"id": "b", "tier": 1, "enabled": True},
                    ],
                },
                f,
            )

        toolbox = MCPToolbox(registry_path=registry_file, allowed_tiers=[1])
        toolbox.load_tools()

        ids = toolbox.list_tool_ids()
        assert ids == ["a", "b", "c"]

    def test_get_tool(self, tmp_path):
        """Test getting a specific tool."""
        registry_file = tmp_path / "registry.yaml"
        import yaml

        with open(registry_file, "w") as f:
            yaml.safe_dump(
                {"version": "v1", "entries": [{"id": "test.tool", "tier": 1, "enabled": True}]},
                f,
            )

        toolbox = MCPToolbox(registry_path=registry_file, allowed_tiers=[1])
        toolbox.load_tools()

        tool = toolbox.get_tool("test.tool")
        assert tool is not None
        assert tool.tool_entry.id == "test.tool"

        not_found = toolbox.get_tool("nonexistent")
        assert not_found is None

    def test_execute_tool(self, tmp_path):
        """Test executing a tool through the toolbox."""
        registry_file = tmp_path / "registry.yaml"
        import yaml

        with open(registry_file, "w") as f:
            yaml.safe_dump(
                {"version": "v1", "entries": [{"id": "test.tool", "tier": 1, "enabled": True}]},
                f,
            )

        toolbox = MCPToolbox(registry_path=registry_file, allowed_tiers=[1])
        toolbox.load_tools()

        result = toolbox.execute_tool(
            "test.tool", {"input": "data"}, {"trace_id": "trace123"}
        )

        assert result["tool"] == "test.tool"
        assert result["status"] == "mock_success"

    def test_execute_nonexistent_tool(self, tmp_path):
        """Test executing a tool that doesn't exist."""
        registry_file = tmp_path / "registry.yaml"
        import yaml

        with open(registry_file, "w") as f:
            yaml.safe_dump({"version": "v1", "entries": []}, f)

        toolbox = MCPToolbox(registry_path=registry_file, allowed_tiers=[1])
        toolbox.load_tools()

        with pytest.raises(KeyError, match="Tool not found"):
            toolbox.execute_tool("nonexistent", {})


class TestCreateMCPToolbox:
    """Test create_mcp_toolbox convenience function."""

    def test_create_toolbox(self, tmp_path):
        """Test creating a toolbox with the convenience function."""
        registry_file = tmp_path / "registry.yaml"
        import yaml

        with open(registry_file, "w") as f:
            yaml.safe_dump(
                {"version": "v1", "entries": [{"id": "test.tool", "tier": 1, "enabled": True}]},
                f,
            )

        toolbox = create_mcp_toolbox(
            allowed_tiers=[1, 2], registry_path=registry_file, deny_by_default=True
        )

        # Tools should already be loaded
        assert len(toolbox._tools) == 1
        assert "test.tool" in toolbox._tools


class TestDeterministicBehavior:
    """Test deterministic behavior across toolbox operations."""

    def test_multiple_loads_produce_same_order(self, tmp_path):
        """Test that multiple loads produce the same tool order."""
        registry_file = tmp_path / "registry.yaml"
        import yaml

        with open(registry_file, "w") as f:
            yaml.safe_dump(
                {
                    "version": "v1",
                    "entries": [
                        {"id": "z", "tier": 1, "enabled": True},
                        {"id": "a", "tier": 1, "enabled": True},
                        {"id": "m", "tier": 1, "enabled": True},
                    ],
                },
                f,
            )

        toolbox1 = MCPToolbox(registry_path=registry_file, allowed_tiers=[1])
        tools1 = toolbox1.load_tools()

        toolbox2 = MCPToolbox(registry_path=registry_file, allowed_tiers=[1])
        tools2 = toolbox2.load_tools()

        ids1 = list(tools1.keys())
        ids2 = list(tools2.keys())

        assert ids1 == ids2
        assert ids1 == sorted(ids1)
