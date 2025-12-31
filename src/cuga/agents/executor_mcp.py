"""MCP-aware executor integration for seamless MCP tool execution.

This module extends the existing executor to support MCP tools while maintaining
compatibility with existing Granite workflows and deterministic execution.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from cuga.agents.registry import ToolRegistry
from cuga.tools.mcp_registry import MCPRegistryLoader
from cuga.tools.mcp_toolbox import MCPToolbox

logger = logging.getLogger(__name__)


class MCPToolRegistryAdapter:
    """Adapts MCPToolbox to work with the existing ToolRegistry interface.
    
    This adapter allows MCP tools to be registered in the existing ToolRegistry
    used by the Executor, enabling seamless integration without breaking existing
    workflows.
    """
    
    def __init__(
        self,
        registry_path: Optional[Path] = None,
        allowed_tiers: Optional[list[int]] = None,
        enable_audit: bool = True,
    ):
        """Initialize the MCP tool registry adapter.
        
        Args:
            registry_path: Path to the MCP registry YAML
            allowed_tiers: List of allowed tier levels
            enable_audit: Whether to enable audit logging
        """
        self.mcp_toolbox = MCPToolbox(
            registry_path=registry_path,
            allowed_tiers=allowed_tiers,
            enable_audit=enable_audit,
        )
        self.mcp_toolbox.load_tools()
    
    def register_mcp_tools(
        self,
        tool_registry: ToolRegistry,
        profile: str,
        tool_ids: Optional[list[str]] = None,
    ) -> None:
        """Register MCP tools into a ToolRegistry for a specific profile.
        
        Args:
            tool_registry: The ToolRegistry to register tools into
            profile: The profile to register tools for
            tool_ids: Optional list of specific tool IDs to register.
                     If None, registers all available tools.
        """
        # Get list of tools to register
        if tool_ids is None:
            tool_ids = self.mcp_toolbox.list_tools()
        
        # Register each tool
        for tool_id in tool_ids:
            try:
                manifest = self.mcp_toolbox.get_tool_manifest(tool_id)
                
                # Create a handler wrapper that calls the MCP toolbox
                def make_handler(tid: str):
                    def handler(inputs: Dict[str, Any], config: Optional[Dict[str, Any]] = None, context: Optional[Any] = None) -> Dict[str, Any]:
                        # Convert execution context to dict if needed
                        ctx_dict = {}
                        if context is not None:
                            if hasattr(context, '__dict__'):
                                ctx_dict = {
                                    'profile': getattr(context, 'profile', profile),
                                    'trace_id': getattr(context, 'trace_id', ''),
                                }
                            elif isinstance(context, dict):
                                ctx_dict = context
                        
                        # Add config to context if provided
                        if config:
                            ctx_dict['config'] = config
                        
                        # Execute via toolbox
                        return self.mcp_toolbox.execute_tool(tid, inputs, ctx_dict)
                    return handler
                
                # Register the tool with the existing registry
                tool_registry.register(
                    profile=profile,
                    name=tool_id,
                    handler=make_handler(tool_id),
                    config={},
                    cost=1.0,  # Default cost, can be overridden
                    latency=1.0,  # Default latency
                    description=f"MCP tool: {tool_id} (tier {manifest.tier})",
                )
                
                logger.debug(f"Registered MCP tool {tool_id} for profile {profile}")
            
            except Exception as e:
                logger.warning(f"Failed to register MCP tool {tool_id}: {e}")
    
    def register_mcp_tools_by_tier(
        self,
        tool_registry: ToolRegistry,
        profile: str,
        tier: int,
    ) -> None:
        """Register all MCP tools of a specific tier.
        
        Args:
            tool_registry: The ToolRegistry to register tools into
            profile: The profile to register tools for
            tier: The tier level to register
        """
        tool_ids = self.mcp_toolbox.get_tools_by_tier(tier)
        self.register_mcp_tools(tool_registry, profile, tool_ids)
    
    def register_mcp_tools_by_scope(
        self,
        tool_registry: ToolRegistry,
        profile: str,
        scope: str,
    ) -> None:
        """Register all MCP tools with a specific scope.
        
        Args:
            tool_registry: The ToolRegistry to register tools into
            profile: The profile to register tools for
            scope: The scope to filter by (e.g., 'fs', 'web', 'vcs')
        """
        tool_ids = self.mcp_toolbox.get_tools_by_scope(scope)
        self.register_mcp_tools(tool_registry, profile, tool_ids)


def create_mcp_enhanced_registry(
    profile: str = "default",
    registry_path: Optional[Path] = None,
    allowed_tiers: Optional[list[int]] = None,
    enable_audit: bool = True,
    include_all_tools: bool = True,
) -> ToolRegistry:
    """Create a ToolRegistry pre-loaded with MCP tools.
    
    This is a convenience function for creating a registry that includes
    MCP tools, useful for testing and simple use cases.
    
    Args:
        profile: The profile to register tools for
        registry_path: Path to the MCP registry YAML
        allowed_tiers: List of allowed tier levels
        enable_audit: Whether to enable audit logging
        include_all_tools: Whether to include all available tools
        
    Returns:
        ToolRegistry with MCP tools registered
    """
    # Create adapter and registry
    adapter = MCPToolRegistryAdapter(
        registry_path=registry_path,
        allowed_tiers=allowed_tiers,
        enable_audit=enable_audit,
    )
    
    tool_registry = ToolRegistry()
    
    # Register MCP tools
    if include_all_tools:
        adapter.register_mcp_tools(tool_registry, profile)
    
    return tool_registry


class MCPExecutorMixin:
    """Mixin to add MCP tool support to Executor.
    
    This mixin can be used to extend the existing Executor class with
    MCP tool loading capabilities while maintaining backward compatibility.
    
    Example:
        class MCPExecutor(MCPExecutorMixin, Executor):
            pass
    """
    
    def load_mcp_tools(
        self,
        registry: ToolRegistry,
        profile: str,
        registry_path: Optional[Path] = None,
        allowed_tiers: Optional[list[int]] = None,
        tool_ids: Optional[list[str]] = None,
    ) -> None:
        """Load MCP tools into the registry for execution.
        
        Args:
            registry: The ToolRegistry to load tools into
            profile: The profile to register tools for
            registry_path: Path to the MCP registry YAML
            allowed_tiers: List of allowed tier levels
            tool_ids: Optional list of specific tool IDs to load
        """
        adapter = MCPToolRegistryAdapter(
            registry_path=registry_path,
            allowed_tiers=allowed_tiers,
            enable_audit=True,
        )
        
        adapter.register_mcp_tools(registry, profile, tool_ids)
        
        logger.info(f"Loaded MCP tools for profile {profile}")
