"""Langflow MCP Client Component for registry-based MCP tool integration.

This component allows Langflow workflows to use MCP tools with tier-based
filtering and guardrails enforcement.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from langflow.custom import custom_component
    from langflow.custom.custom_component.component import Component
    from langflow.schema import Data
except Exception:  # pragma: no cover - soft dependency
    Component = object  # type: ignore
    custom_component = lambda *args, **kwargs: (lambda cls: cls)
    Data = dict  # type: ignore

from cuga.tools.mcp_registry import MCPRegistryLoader
from cuga.tools.mcp_toolbox import MCPToolbox, create_toolbox


@custom_component(
    component_type="tool_provider",
    description="Provides MCP tools with tier-based filtering and guardrails"
)
class MCPClientComponent(Component):
    """Langflow component for MCP tool integration.
    
    This component loads MCP tools from the registry, applies tier-based
    filtering, and generates guarded tool wrappers for use in Langflow
    workflows.
    
    Inputs:
        - registry_path: Path to MCP registry YAML file (optional)
        - allowed_tiers: Comma-separated tier numbers (e.g., "1,2")
        - tool_ids: Comma-separated tool IDs to include (optional)
        - enable_guards: Whether to enable default guards
        - enable_audit: Whether to enable audit logging
    
    Outputs:
        - tools: List of available MCP tools with metadata
        - toolbox: MCPToolbox instance for tool execution
    """
    
    display_name = "MCP Client"
    description = "Load and filter MCP tools from registry"
    
    def build_config(self) -> Dict[str, Any]:  # pragma: no cover - UI metadata
        return {
            "registry_path": {
                "type": "str",
                "required": False,
                "display_name": "Registry Path",
                "info": "Path to MCP registry YAML file (uses default if not provided)",
            },
            "allowed_tiers": {
                "type": "str",
                "required": False,
                "display_name": "Allowed Tiers",
                "info": "Comma-separated tier numbers (e.g., '1,2'). Empty = all tiers.",
                "default": "1",
            },
            "tool_ids": {
                "type": "str",
                "required": False,
                "display_name": "Tool IDs",
                "info": "Comma-separated tool IDs to include (e.g., 'mcp.github,mcp.fs'). Empty = all available tools.",
            },
            "enable_guards": {
                "type": "bool",
                "required": False,
                "display_name": "Enable Guards",
                "info": "Enable default guard checks (sandbox, tier, budget)",
                "default": True,
            },
            "enable_audit": {
                "type": "bool",
                "required": False,
                "display_name": "Enable Audit",
                "info": "Enable audit logging for tool executions",
                "default": True,
            },
        }
    
    def __call__(
        self,
        registry_path: Optional[str] = None,
        allowed_tiers: str = "1",
        tool_ids: Optional[str] = None,
        enable_guards: bool = True,
        enable_audit: bool = True,
    ) -> Dict[str, Any]:
        """Load and filter MCP tools.
        
        Args:
            registry_path: Path to registry YAML (optional)
            allowed_tiers: Comma-separated tier numbers
            tool_ids: Comma-separated tool IDs (optional)
            enable_guards: Whether to enable guards
            enable_audit: Whether to enable audit logging
            
        Returns:
            Dictionary with 'tools' list and 'toolbox' instance
        """
        # Parse registry path
        reg_path = Path(registry_path) if registry_path else None
        
        # Parse allowed tiers
        tiers = None
        if allowed_tiers:
            try:
                tiers = [int(t.strip()) for t in allowed_tiers.split(",") if t.strip()]
            except ValueError:
                tiers = [1]  # Default to tier 1 on parse error
        
        # Create toolbox
        toolbox = create_toolbox(
            registry_path=reg_path,
            allowed_tiers=tiers,
            enable_audit=enable_audit,
            enable_guards=enable_guards,
        )
        
        # Get tool list
        if tool_ids:
            # Filter to specific tools
            requested_ids = [tid.strip() for tid in tool_ids.split(",") if tid.strip()]
            available_tools = [tid for tid in requested_ids if toolbox.has_tool(tid)]
        else:
            # Get all tools
            available_tools = toolbox.list_tools()
        
        # Build tool metadata list
        tools_metadata = []
        for tool_id in available_tools:
            try:
                manifest = toolbox.get_tool_manifest(tool_id)
                tools_metadata.append({
                    "id": manifest.id,
                    "tier": manifest.tier,
                    "protocol": manifest.protocol,
                    "sandbox": manifest.sandbox,
                    "scopes": manifest.scopes,
                    "description": f"MCP tool: {manifest.id} (tier {manifest.tier})",
                })
            except Exception:
                # Skip tools that can't be loaded
                continue
        
        return {
            "tools": tools_metadata,
            "toolbox": toolbox,
            "tool_count": len(tools_metadata),
        }
    
    def has_tool(self, tool_id: str) -> bool:
        """Check if a tool is available in the loaded toolbox.
        
        Args:
            tool_id: The tool identifier
            
        Returns:
            True if tool is available
        """
        # Access the toolbox from the last execution
        # In practice, this would be used in a stateful workflow context
        return False  # Placeholder - would need workflow state management


@custom_component(
    component_type="tool_executor",
    description="Execute MCP tools from the client"
)
class MCPToolExecutorComponent(Component):
    """Langflow component for executing MCP tools.
    
    This component takes a toolbox from MCPClientComponent and executes
    a specific tool with given inputs.
    
    Inputs:
        - toolbox: MCPToolbox instance from MCPClientComponent
        - tool_id: Tool identifier to execute
        - inputs: Tool input parameters (dict)
        - context: Execution context (dict, optional)
    
    Outputs:
        - result: Tool execution results
        - status: Execution status
    """
    
    display_name = "MCP Tool Executor"
    description = "Execute an MCP tool from the toolbox"
    
    def build_config(self) -> Dict[str, Any]:  # pragma: no cover - UI metadata
        return {
            "toolbox": {
                "type": "object",
                "required": True,
                "display_name": "Toolbox",
                "info": "MCPToolbox instance from MCP Client component",
            },
            "tool_id": {
                "type": "str",
                "required": True,
                "display_name": "Tool ID",
                "info": "MCP tool identifier (e.g., 'mcp.github')",
            },
            "inputs": {
                "type": "dict",
                "required": True,
                "display_name": "Inputs",
                "info": "Tool input parameters as dictionary",
            },
            "context": {
                "type": "dict",
                "required": False,
                "display_name": "Context",
                "info": "Execution context (trace_id, user_id, etc.)",
            },
        }
    
    def __call__(
        self,
        toolbox: Any,
        tool_id: str,
        inputs: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute an MCP tool.
        
        Args:
            toolbox: MCPToolbox instance
            tool_id: Tool identifier
            inputs: Tool inputs
            context: Execution context
            
        Returns:
            Execution results with status
        """
        try:
            # Execute the tool
            result = toolbox.execute_tool(tool_id, inputs, context or {})
            
            return {
                "result": result,
                "status": "success",
                "tool_id": tool_id,
            }
        except Exception as e:
            return {
                "result": None,
                "status": "error",
                "error": str(e),
                "tool_id": tool_id,
            }


def create_mcp_langflow_components() -> List[type]:
    """Factory function to create MCP Langflow components.
    
    Returns:
        List of component classes for registration
    """
    return [MCPClientComponent, MCPToolExecutorComponent]
