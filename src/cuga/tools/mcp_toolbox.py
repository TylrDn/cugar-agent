"""MCP Toolbox with guardrails, audit, and determinism enforcement.

This module provides the core toolbox for loading, wrapping, and executing
MCP tools with guardrails, audit logging, and deterministic output handling.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from cuga.observability.mcp_audit import AuditContext, MCPAuditLogger
from cuga.tools.mcp_registry import MCPRegistryLoader, MCPToolManifest

logger = logging.getLogger(__name__)


class MCPToolboxError(Exception):
    """Base exception for toolbox errors."""
    pass


class ToolExecutionError(MCPToolboxError):
    """Raised when tool execution fails."""
    pass


class GuardCheckError(MCPToolboxError):
    """Raised when guard checks fail."""
    pass


class MCPToolWrapper:
    """Wrapper for MCP tools with guard checks and audit logging."""
    
    def __init__(
        self,
        manifest: MCPToolManifest,
        handler: Optional[Callable] = None,
        audit_logger: Optional[MCPAuditLogger] = None,
        guards: Optional[List[Callable]] = None,
    ):
        """Initialize tool wrapper.
        
        Args:
            manifest: The tool manifest
            handler: Optional tool handler function
            audit_logger: Optional audit logger
            guards: Optional list of guard check functions
        """
        self.manifest = manifest
        self.handler = handler
        self.audit_logger = audit_logger
        self.guards = guards or []
    
    def execute(
        self,
        inputs: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute the tool with guards and auditing.
        
        Args:
            inputs: Tool input parameters
            context: Execution context (trace_id, user_id, etc.)
            
        Returns:
            Tool execution results
            
        Raises:
            GuardCheckError: If guard checks fail
            ToolExecutionError: If execution fails
        """
        context = context or {}
        
        # Run guard checks
        self._run_guards(inputs, context)
        
        # Execute with audit logging
        if self.audit_logger:
            with AuditContext(
                self.audit_logger,
                self.manifest.id,
                inputs,
                metadata=context,
            ) as audit_ctx:
                try:
                    result = self._execute_handler(inputs, context)
                    audit_ctx.set_outputs(result)
                    return result
                except Exception as e:
                    audit_ctx.set_error(str(e))
                    raise ToolExecutionError(f"Tool {self.manifest.id} failed: {e}") from e
        else:
            try:
                return self._execute_handler(inputs, context)
            except Exception as e:
                raise ToolExecutionError(f"Tool {self.manifest.id} failed: {e}") from e
    
    def _run_guards(self, inputs: Dict[str, Any], context: Dict[str, Any]) -> None:
        """Run guard checks on inputs.
        
        Args:
            inputs: Tool inputs
            context: Execution context
            
        Raises:
            GuardCheckError: If any guard fails
        """
        for guard in self.guards:
            try:
                guard(self.manifest, inputs, context)
            except Exception as e:
                raise GuardCheckError(f"Guard check failed for {self.manifest.id}: {e}") from e
    
    def _execute_handler(
        self,
        inputs: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute the actual tool handler.
        
        Args:
            inputs: Tool inputs
            context: Execution context
            
        Returns:
            Tool results
        """
        if self.handler is None:
            # Return a mock result if no handler is provided
            return {
                "status": "not_implemented",
                "tool_id": self.manifest.id,
                "message": f"Handler not implemented for {self.manifest.id}",
            }
        
        return self.handler(inputs, context)


class MCPToolbox:
    """MCP Toolbox for loading, wrapping, and executing MCP tools.
    
    Features:
    - Registry-based tool loading
    - Deny-by-default access control
    - Guard check enforcement
    - Audit logging
    - Deterministic output normalization
    - Tier-based filtering
    """
    
    def __init__(
        self,
        registry_path: Optional[Path] = None,
        allowed_tiers: Optional[List[int]] = None,
        audit_logger: Optional[MCPAuditLogger] = None,
        enable_audit: bool = True,
    ):
        """Initialize the MCP toolbox.
        
        Args:
            registry_path: Path to the registry YAML file
            allowed_tiers: List of allowed tier levels
            audit_logger: Optional custom audit logger
            enable_audit: Whether to enable audit logging
        """
        self.registry = MCPRegistryLoader(registry_path, allowed_tiers)
        self.registry.load()
        
        if enable_audit:
            self.audit_logger = audit_logger or MCPAuditLogger()
        else:
            self.audit_logger = None
        
        self._tools: Dict[str, MCPToolWrapper] = {}
        self._guards: List[Callable] = []
        self._loaded = False
    
    def load_tools(self) -> None:
        """Load all tools from the registry."""
        if self._loaded:
            return
        
        manifests = self.registry.list_manifests()
        
        for manifest in manifests:
            wrapper = MCPToolWrapper(
                manifest=manifest,
                handler=None,  # Will be set by register_handler
                audit_logger=self.audit_logger,
                guards=self._guards.copy(),
            )
            self._tools[manifest.id] = wrapper
        
        self._loaded = True
        
        if self.audit_logger:
            self.audit_logger.log_event(
                "toolbox_initialized",
                {
                    "tool_count": len(self._tools),
                    "tool_ids": sorted(self._tools.keys()),
                },
            )
        
        logger.info(f"Loaded {len(self._tools)} tools into toolbox")
    
    def register_handler(
        self,
        tool_id: str,
        handler: Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]],
    ) -> None:
        """Register a handler for a specific tool.
        
        Args:
            tool_id: The tool identifier
            handler: The handler function (inputs, context) -> results
        """
        if not self._loaded:
            self.load_tools()
        
        if tool_id not in self._tools:
            raise MCPToolboxError(f"Tool {tool_id} not registered in toolbox")
        
        self._tools[tool_id].handler = handler
        logger.debug(f"Registered handler for {tool_id}")
    
    def add_guard(self, guard: Callable) -> None:
        """Add a global guard check that applies to all tools.
        
        Args:
            guard: Guard function (manifest, inputs, context) -> None
                  Should raise an exception if the check fails.
        """
        self._guards.append(guard)
        
        # Update existing tools with new guard
        for wrapper in self._tools.values():
            if guard not in wrapper.guards:
                wrapper.guards.append(guard)
        
        logger.debug(f"Added global guard: {guard.__name__}")
    
    def execute_tool(
        self,
        tool_id: str,
        inputs: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute a tool by ID.
        
        Args:
            tool_id: The tool identifier
            inputs: Tool input parameters
            context: Execution context
            
        Returns:
            Tool execution results
            
        Raises:
            MCPToolboxError: If tool not found
            GuardCheckError: If guard checks fail
            ToolExecutionError: If execution fails
        """
        if not self._loaded:
            self.load_tools()
        
        wrapper = self._tools.get(tool_id)
        if wrapper is None:
            raise MCPToolboxError(f"Tool {tool_id} not available in toolbox")
        
        return wrapper.execute(inputs, context)
    
    def list_tools(self) -> List[str]:
        """List all available tool IDs in stable order.
        
        Returns:
            Sorted list of tool IDs
        """
        if not self._loaded:
            self.load_tools()
        
        return sorted(self._tools.keys())
    
    def has_tool(self, tool_id: str) -> bool:
        """Check if a tool is available in the toolbox.
        
        Args:
            tool_id: The tool identifier
            
        Returns:
            True if tool is available
        """
        if not self._loaded:
            self.load_tools()
        
        return tool_id in self._tools
    
    def get_tool_manifest(self, tool_id: str) -> MCPToolManifest:
        """Get the manifest for a specific tool.
        
        Args:
            tool_id: The tool identifier
            
        Returns:
            The tool manifest
            
        Raises:
            MCPToolboxError: If tool not found
        """
        if not self._loaded:
            self.load_tools()
        
        wrapper = self._tools.get(tool_id)
        if wrapper is None:
            raise MCPToolboxError(f"Tool {tool_id} not available in toolbox")
        
        return wrapper.manifest
    
    def get_tools_by_tier(self, tier: int) -> List[str]:
        """Get all tool IDs for a specific tier.
        
        Args:
            tier: The tier level
            
        Returns:
            Sorted list of tool IDs
        """
        if not self._loaded:
            self.load_tools()
        
        return sorted([
            tool_id for tool_id, wrapper in self._tools.items()
            if wrapper.manifest.tier == tier
        ])
    
    def get_tools_by_scope(self, scope: str) -> List[str]:
        """Get all tool IDs that include a specific scope.
        
        Args:
            scope: The scope to filter by
            
        Returns:
            Sorted list of tool IDs
        """
        if not self._loaded:
            self.load_tools()
        
        return sorted([
            tool_id for tool_id, wrapper in self._tools.items()
            if scope in wrapper.manifest.scopes
        ])
    
    def close(self) -> None:
        """Close the toolbox and flush audit logs."""
        if self.audit_logger:
            self.audit_logger.close()


# Built-in guard functions

def sandbox_guard(
    manifest: MCPToolManifest,
    inputs: Dict[str, Any],
    context: Dict[str, Any],
) -> None:
    """Guard that validates sandbox configuration.
    
    Args:
        manifest: Tool manifest
        inputs: Tool inputs
        context: Execution context
        
    Raises:
        GuardCheckError: If sandbox validation fails
    """
    # Ensure tool has a valid sandbox
    if not manifest.sandbox:
        raise GuardCheckError(f"Tool {manifest.id} has no sandbox configured")
    
    # Validate sandbox type
    valid_sandboxes = ["py-slim", "py-full", "node-slim", "node-full", "orchestrator"]
    if manifest.sandbox not in valid_sandboxes:
        raise GuardCheckError(
            f"Tool {manifest.id} has invalid sandbox: {manifest.sandbox}. "
            f"Must be one of {valid_sandboxes}"
        )


def tier_guard(
    manifest: MCPToolManifest,
    inputs: Dict[str, Any],
    context: Dict[str, Any],
) -> None:
    """Guard that validates tier access.
    
    Args:
        manifest: Tool manifest
        inputs: Tool inputs
        context: Execution context
        
    Raises:
        GuardCheckError: If tier validation fails
    """
    # Check if tier is explicitly allowed in context
    allowed_tiers = context.get("allowed_tiers")
    if allowed_tiers is not None:
        if manifest.tier not in allowed_tiers:
            raise GuardCheckError(
                f"Tool {manifest.id} tier {manifest.tier} not in allowed tiers: {allowed_tiers}"
            )


def budget_guard(
    manifest: MCPToolManifest,
    inputs: Dict[str, Any],
    context: Dict[str, Any],
) -> None:
    """Guard that enforces budget policy.
    
    Args:
        manifest: Tool manifest
        inputs: Tool inputs
        context: Execution context
        
    Raises:
        GuardCheckError: If budget validation fails
    """
    budget_policy = manifest.budget_policy
    current_cost = context.get("total_cost", 0.0)
    budget_ceiling = context.get("budget_ceiling", 100.0)
    
    if budget_policy == "block" and current_cost >= budget_ceiling:
        raise GuardCheckError(
            f"Budget ceiling reached: {current_cost} >= {budget_ceiling}"
        )
    elif budget_policy == "warn" and current_cost >= budget_ceiling:
        logger.warning(
            f"Budget warning for {manifest.id}: {current_cost} >= {budget_ceiling}"
        )


def create_toolbox(
    registry_path: Optional[Path] = None,
    allowed_tiers: Optional[List[int]] = None,
    enable_audit: bool = True,
    enable_guards: bool = True,
) -> MCPToolbox:
    """Convenience function to create and configure an MCP toolbox.
    
    Args:
        registry_path: Path to the registry YAML file
        allowed_tiers: List of allowed tier levels
        enable_audit: Whether to enable audit logging
        enable_guards: Whether to enable default guards
        
    Returns:
        Configured MCPToolbox instance
    """
    toolbox = MCPToolbox(
        registry_path=registry_path,
        allowed_tiers=allowed_tiers,
        enable_audit=enable_audit,
    )
    
    if enable_guards:
        toolbox.add_guard(sandbox_guard)
        toolbox.add_guard(tier_guard)
        toolbox.add_guard(budget_guard)
    
    toolbox.load_tools()
    
    return toolbox
