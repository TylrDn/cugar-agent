"""Langflow MCP Client Component for loading guarded MCP tools."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MCPClientComponent:
    """
    Langflow component for loading MCP tools with guard enforcement.
    
    Inputs:
        - mcp_servers: Path to MCP registry file
        - allowed_tiers: List of allowed tier numbers (e.g., [1, 2])
        - deny_by_default: Only load explicitly enabled tools
        - audit_file: Path to audit log file (optional)
        
    Outputs:
        - tools: Dictionary of guarded MCP tools
        - tool_ids: List of available tool IDs (sorted)
        - statistics: Tool statistics by tier
    """

    display_name = "MCP Client"
    description = "Load MCP tools with tier-based security and guard enforcement"
    category = "Tools"

    def __init__(
        self,
        mcp_servers: str = "",
        allowed_tiers: List[int] = None,
        deny_by_default: bool = True,
        audit_file: str = "",
    ):
        """
        Initialize the MCP client component.
        
        Args:
            mcp_servers: Path to MCP registry YAML file
            allowed_tiers: List of allowed tier numbers
            deny_by_default: If True, only load explicitly enabled tools
            audit_file: Path to audit log file (optional)
        """
        self.mcp_servers = mcp_servers
        self.allowed_tiers = allowed_tiers or [1]
        self.deny_by_default = deny_by_default
        self.audit_file = audit_file
        self._toolbox: Optional[Any] = None
        self._loaded = False

    def build(self) -> Dict[str, Any]:
        """
        Build and return the MCP toolbox with guarded tools.
        
        Returns:
            Dictionary containing:
                - tools: Guarded MCP tools
                - tool_ids: List of tool IDs
                - statistics: Tool statistics
        """
        try:
            from cuga.tools.mcp_toolbox import create_mcp_toolbox

            # Parse registry path
            registry_path = None
            if self.mcp_servers:
                registry_path = Path(self.mcp_servers)

            # Parse audit file path
            audit_file_path = None
            if self.audit_file:
                audit_file_path = Path(self.audit_file)

            # Create toolbox
            self._toolbox = create_mcp_toolbox(
                allowed_tiers=self.allowed_tiers,
                registry_path=registry_path,
                audit_file=audit_file_path,
                deny_by_default=self.deny_by_default,
            )

            self._loaded = True

            # Get tool statistics
            manifest = self._toolbox.registry_loader.get_manifest()
            if manifest:
                tier_counts = manifest.get_tier_counts()
            else:
                tier_counts = {}

            return {
                "tools": self._toolbox._tools,
                "tool_ids": self._toolbox.list_tool_ids(),
                "statistics": {
                    "total_tools": len(self._toolbox._tools),
                    "allowed_tiers": self.allowed_tiers,
                    "tiers": tier_counts,
                    "deny_by_default": self.deny_by_default,
                },
            }

        except Exception as e:
            logger.error(f"Failed to build MCP client: {e}")
            return {
                "tools": {},
                "tool_ids": [],
                "statistics": {"error": str(e)},
            }

    def execute_tool(
        self, tool_id: str, input: Dict[str, Any], context: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Execute a specific tool through the toolbox.
        
        Args:
            tool_id: Tool identifier
            input: Tool input parameters
            context: Execution context (optional)
            
        Returns:
            Tool execution result
            
        Raises:
            RuntimeError: If toolbox not loaded or tool execution fails
        """
        if not self._loaded or self._toolbox is None:
            raise RuntimeError("MCP toolbox not loaded. Call build() first.")

        return self._toolbox.execute_tool(tool_id, input, context)

    def get_tools(self) -> Dict[str, Any]:
        """Get loaded tools dictionary."""
        if not self._loaded or self._toolbox is None:
            return {}
        return self._toolbox._tools

    def list_tool_ids(self) -> List[str]:
        """List available tool IDs in deterministic order."""
        if not self._loaded or self._toolbox is None:
            return []
        return self._toolbox.list_tool_ids()


# Langflow component registration metadata
component_metadata = {
    "display_name": "MCP Client",
    "description": "Load MCP tools with tier-based security and guard enforcement",
    "category": "Tools",
    "inputs": [
        {
            "name": "mcp_servers",
            "display_name": "MCP Registry File",
            "type": "str",
            "required": False,
            "info": "Path to MCP registry YAML file",
        },
        {
            "name": "allowed_tiers",
            "display_name": "Allowed Tiers",
            "type": "list",
            "required": False,
            "info": "List of allowed tier numbers (e.g., [1, 2])",
        },
        {
            "name": "deny_by_default",
            "display_name": "Deny By Default",
            "type": "bool",
            "required": False,
            "info": "Only load explicitly enabled tools",
        },
        {
            "name": "audit_file",
            "display_name": "Audit Log File",
            "type": "str",
            "required": False,
            "info": "Path to audit log file (optional)",
        },
    ],
    "outputs": [
        {
            "name": "tools",
            "display_name": "MCP Tools",
            "type": "dict",
            "info": "Dictionary of guarded MCP tools",
        },
        {
            "name": "tool_ids",
            "display_name": "Tool IDs",
            "type": "list",
            "info": "List of available tool IDs (sorted)",
        },
        {
            "name": "statistics",
            "display_name": "Statistics",
            "type": "dict",
            "info": "Tool statistics by tier",
        },
    ],
}
