"""MCP Toolbox with guard enforcement, audit logging, and deterministic tool loading."""

from __future__ import annotations

import logging
import time
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from cuga.guards.tool_guard import ToolGuard
from cuga.observability.mcp_audit import MCPAuditLogger, get_audit_logger
from cuga.tools.mcp_registry import MCPRegistryLoader, MCPToolEntry, load_mcp_manifest

logger = logging.getLogger(__name__)


class GuardedMCPTool:
    """
    Wrapper for an MCP tool with guard enforcement and audit logging.
    """

    def __init__(
        self,
        tool_entry: MCPToolEntry,
        handler: Callable[[Dict[str, Any]], Any],
        guard: ToolGuard,
        audit_logger: MCPAuditLogger,
    ):
        """
        Initialize a guarded MCP tool.

        Args:
            tool_entry: Tool metadata from registry
            handler: The actual tool implementation function
            guard: Guard to check before execution
            audit_logger: Logger for audit trail
        """
        self.tool_entry = tool_entry
        self.handler = handler
        self.guard = guard
        self.audit_logger = audit_logger

    def __call__(self, input: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Any:
        """
        Execute the tool with guard checking and audit logging.

        Args:
            input: Tool input parameters
            context: Execution context (trace_id, profile, etc.)

        Returns:
            Tool output

        Raises:
            RuntimeError: If guard check fails
        """
        if context is None:
            context = {}

        trace_id = context.get("trace_id", "")
        profile = context.get("profile", "default")

        # Guard check
        guard_payload = {
            "tool": self.tool_entry.id,
            "tier": self.tool_entry.tier,
            "scopes": self.tool_entry.scopes,
            "readonly": "write" not in self.tool_entry.scopes,
            "input": input,
        }

        guard_result = self.guard.evaluate(guard_payload)

        if guard_result.decision == "fail":
            error_msg = f"Guard check failed for tool {self.tool_entry.id}: {guard_result.details}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        # Log invocation
        audit_record = self.audit_logger.log_invocation(
            tool_id=self.tool_entry.id,
            method="execute",
            input=input,
            trace_id=trace_id,
            profile=profile,
            tier=self.tool_entry.tier,
        )

        start_time = time.time()

        try:
            # Execute the tool
            result = self.handler(input)

            duration_ms = (time.time() - start_time) * 1000

            # Log completion
            self.audit_logger.log_completion(
                record=audit_record,
                output=result,
                duration_ms=duration_ms,
                cost=self.tool_entry.constraints.get("cost", 0.0),
                latency=self.tool_entry.constraints.get("latency", 0.0),
            )

            return result

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000

            # Log error
            self.audit_logger.log_error(
                record=audit_record,
                error=str(e),
                duration_ms=duration_ms,
            )

            raise


class MCPToolbox:
    """
    Central toolbox for loading and managing MCP tools with security and audit.
    """

    def __init__(
        self,
        registry_path: Optional[Path] = None,
        audit_file: Optional[Path] = None,
        allowed_tiers: Optional[List[int]] = None,
        deny_by_default: bool = True,
    ):
        """
        Initialize the MCP toolbox.

        Args:
            registry_path: Path to registry.yaml file
            audit_file: Path to audit log file
            allowed_tiers: List of allowed tier numbers (e.g., [1, 2])
            deny_by_default: If True, only load explicitly enabled tools
        """
        self.registry_loader = MCPRegistryLoader(
            registry_path=registry_path, deny_by_default=deny_by_default
        )
        self.audit_logger = get_audit_logger(audit_file=audit_file)
        self.guard = ToolGuard()
        self.allowed_tiers = allowed_tiers or [1]  # Default to tier 1 only
        self._tools: Dict[str, GuardedMCPTool] = {}

    def load_tools(self) -> Dict[str, GuardedMCPTool]:
        """
        Load tools from registry with guard enforcement.
        Returns tools in deterministic order (sorted by ID).

        Returns:
            Dictionary mapping tool ID to GuardedMCPTool
        """
        manifest = self.registry_loader.load()

        # Filter by allowed tiers
        max_tier = max(self.allowed_tiers) if self.allowed_tiers else 3
        tools = manifest.list_tools(tier=max_tier, enabled_only=True, sorted_by_id=True)

        for tool_entry in tools:
            # Create a mock handler for now (will be replaced with actual MCP adapter)
            handler = self._create_mock_handler(tool_entry)

            guarded_tool = GuardedMCPTool(
                tool_entry=tool_entry,
                handler=handler,
                guard=self.guard,
                audit_logger=self.audit_logger,
            )

            self._tools[tool_entry.id] = guarded_tool

        logger.info(
            f"Loaded {len(self._tools)} MCP tools (tiers: {self.allowed_tiers}, "
            f"deny_by_default: {self.registry_loader.deny_by_default})"
        )

        return self._tools

    def _create_mock_handler(self, tool_entry: MCPToolEntry) -> Callable[[Dict[str, Any]], Any]:
        """Create a mock handler for testing (to be replaced with real MCP adapter)."""

        def mock_handler(input: Dict[str, Any]) -> Dict[str, Any]:
            """Mock handler that returns deterministic output."""
            return {
                "tool": tool_entry.id,
                "tier": tool_entry.tier,
                "sandbox": tool_entry.sandbox,
                "input_received": input,
                "status": "mock_success",
            }

        return mock_handler

    def get_tool(self, tool_id: str) -> Optional[GuardedMCPTool]:
        """Get a specific tool by ID."""
        return self._tools.get(tool_id)

    def list_tool_ids(self) -> List[str]:
        """List all loaded tool IDs in deterministic order."""
        return sorted(self._tools.keys())

    def get_tools_by_tier(self, tier: int) -> List[GuardedMCPTool]:
        """Get all tools for a specific tier."""
        return [tool for tool in self._tools.values() if tool.tool_entry.tier == tier]

    def execute_tool(
        self, tool_id: str, input: Dict[str, Any], context: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Execute a tool by ID with guard and audit.

        Args:
            tool_id: Tool identifier
            input: Tool input parameters
            context: Execution context

        Returns:
            Tool output

        Raises:
            KeyError: If tool not found
            RuntimeError: If guard check fails or execution error
        """
        tool = self.get_tool(tool_id)
        if tool is None:
            raise KeyError(f"Tool not found: {tool_id}")

        return tool(input, context)


def create_mcp_toolbox(
    allowed_tiers: Optional[List[int]] = None,
    registry_path: Optional[Path] = None,
    audit_file: Optional[Path] = None,
    deny_by_default: bool = True,
) -> MCPToolbox:
    """
    Convenience function to create and initialize an MCP toolbox.

    Args:
        allowed_tiers: List of allowed tier numbers (e.g., [1, 2])
        registry_path: Path to registry.yaml file
        audit_file: Path to audit log file
        deny_by_default: If True, only load explicitly enabled tools

    Returns:
        Initialized MCPToolbox with tools loaded
    """
    toolbox = MCPToolbox(
        registry_path=registry_path,
        audit_file=audit_file,
        allowed_tiers=allowed_tiers,
        deny_by_default=deny_by_default,
    )
    toolbox.load_tools()
    return toolbox
