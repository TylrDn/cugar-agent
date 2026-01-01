"""MCP Router - Capability-based routing for MCP clients.

This module provides a minimal router implementation for mapping agent requests
to appropriate MCP clients based on capabilities and intents.

This is a stub implementation focused on establishing the architecture for:
- Parsing incoming agent requests
- Mapping intents/categories to MCP clients
- Pluggable approval policy enforcement

Future iterations will add:
- Full routing logic with capability matching
- Fallback strategies
- Advanced policy enforcement
- Load balancing and health-aware routing
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol

logger = logging.getLogger(__name__)


class TransportType(Enum):
    """MCP transport types."""
    HTTP = "http"
    STDIO = "stdio"
    EMBEDDED = "embedded"


@dataclass
class MCPCapability:
    """Represents a capability provided by an MCP server.
    
    Attributes:
        action: The action type (e.g., "read", "write", "compute")
        auth: Authentication requirement (e.g., "none", "token-required")
        description: Human-readable description
    """
    action: str
    auth: str = "none"
    description: str = ""


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server.
    
    Attributes:
        name: Server name/identifier
        transport: Transport type (http, stdio, embedded)
        capabilities: List of server capabilities
        permission_scope: Permission level (read-only, read-write, etc.)
        metadata: Additional server metadata
    """
    name: str
    transport: TransportType
    capabilities: List[MCPCapability] = field(default_factory=list)
    permission_scope: str = "read-only"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentRequest:
    """Represents an incoming agent request.
    
    Attributes:
        intent: The user's intent/goal
        category: Request category (e.g., "data", "compute", "api")
        required_capabilities: List of required capability actions
        context: Additional request context
    """
    intent: str
    category: str = "general"
    required_capabilities: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RoutingDecision:
    """Represents a routing decision.
    
    Attributes:
        server: Selected MCP server configuration
        reason: Reason for selection
        confidence: Confidence score (0.0-1.0)
        requires_approval: Whether this decision requires approval
    """
    server: MCPServerConfig
    reason: str
    confidence: float = 1.0
    requires_approval: bool = False


class ApprovalPolicy(Protocol):
    """Protocol for approval policy implementations."""
    
    def requires_approval(
        self,
        request: AgentRequest,
        decision: RoutingDecision,
    ) -> bool:
        """Check if a routing decision requires approval.
        
        Args:
            request: The agent request
            decision: The routing decision
            
        Returns:
            True if approval is required, False otherwise
        """
        ...
    
    def request_approval(
        self,
        request: AgentRequest,
        decision: RoutingDecision,
    ) -> bool:
        """Request approval for a routing decision.
        
        Args:
            request: The agent request
            decision: The routing decision
            
        Returns:
            True if approved, False otherwise
        """
        ...


class MCPRouter:
    """Capability-based router for MCP clients.
    
    This router maps incoming agent requests to appropriate MCP servers
    based on capabilities, intents, and approval policies.
    
    This is a minimal stub implementation establishing the architecture.
    """
    
    def __init__(
        self,
        servers: Optional[List[MCPServerConfig]] = None,
        approval_policy: Optional[ApprovalPolicy] = None,
    ) -> None:
        """Initialize the MCP router.
        
        Args:
            servers: List of available MCP server configurations
            approval_policy: Optional approval policy for routing decisions
        """
        self.servers = servers or []
        self.approval_policy = approval_policy
        logger.info(f"Initialized MCPRouter with {len(self.servers)} servers")
    
    def add_server(self, server: MCPServerConfig) -> None:
        """Register an MCP server with the router.
        
        Args:
            server: MCP server configuration to register
        """
        self.servers.append(server)
        logger.info(f"Registered MCP server: {server.name} ({server.transport.value})")
    
    def route_request(self, request: AgentRequest) -> Optional[RoutingDecision]:
        """Route an agent request to an appropriate MCP server.
        
        This is a stub implementation that establishes the routing interface.
        Future iterations will implement full capability matching logic.
        
        Args:
            request: The agent request to route
            
        Returns:
            Routing decision or None if no suitable server found
        """
        logger.info(f"Routing request with intent: {request.intent}")
        
        # Stub: Find servers matching required capabilities
        matching_servers = self._find_matching_servers(request)
        
        if not matching_servers:
            logger.warning(f"No matching servers found for request: {request.intent}")
            return None
        
        # Stub: Select the first matching server (simple selection strategy)
        selected_server = matching_servers[0]
        
        decision = RoutingDecision(
            server=selected_server,
            reason=f"Selected based on capability match",
            confidence=0.8,  # Stub confidence value
            requires_approval=self._check_approval_required(request, selected_server),
        )
        
        logger.info(
            f"Routed to server: {selected_server.name} "
            f"(confidence: {decision.confidence:.2f})"
        )
        
        return decision
    
    def _find_matching_servers(self, request: AgentRequest) -> List[MCPServerConfig]:
        """Find servers matching the request capabilities.
        
        This is a stub implementation with basic matching logic.
        
        Args:
            request: The agent request
            
        Returns:
            List of matching server configurations
        """
        if not request.required_capabilities:
            # No specific capabilities required, return all servers
            return self.servers
        
        matching = []
        for server in self.servers:
            server_capabilities = {cap.action for cap in server.capabilities}
            
            # Check if server provides all required capabilities
            if all(cap in server_capabilities for cap in request.required_capabilities):
                matching.append(server)
        
        return matching
    
    def _check_approval_required(
        self,
        request: AgentRequest,
        server: MCPServerConfig,
    ) -> bool:
        """Check if approval is required for this routing decision.
        
        Args:
            request: The agent request
            server: The selected server
            
        Returns:
            True if approval is required, False otherwise
        """
        if self.approval_policy is None:
            return False
        
        decision = RoutingDecision(
            server=server,
            reason="Checking approval requirement",
            confidence=1.0,
        )
        
        return self.approval_policy.requires_approval(request, decision)
    
    def get_server_by_name(self, name: str) -> Optional[MCPServerConfig]:
        """Get a server configuration by name.
        
        Args:
            name: Server name
            
        Returns:
            Server configuration or None if not found
        """
        for server in self.servers:
            if server.name == name:
                return server
        return None
    
    def list_servers(self) -> List[MCPServerConfig]:
        """List all registered servers.
        
        Returns:
            List of all server configurations
        """
        return self.servers.copy()
    
    def get_servers_by_capability(self, capability: str) -> List[MCPServerConfig]:
        """Get servers that provide a specific capability.
        
        Args:
            capability: Capability action to search for
            
        Returns:
            List of servers providing the capability
        """
        matching = []
        for server in self.servers:
            if any(cap.action == capability for cap in server.capabilities):
                matching.append(server)
        return matching
    
    def get_servers_by_transport(self, transport: TransportType) -> List[MCPServerConfig]:
        """Get servers using a specific transport type.
        
        Args:
            transport: Transport type to filter by
            
        Returns:
            List of servers using the transport
        """
        return [s for s in self.servers if s.transport == transport]


# Stub approval policy implementation
class DefaultApprovalPolicy:
    """Default approval policy implementation.
    
    This is a stub that demonstrates the approval policy interface.
    """
    
    def requires_approval(
        self,
        request: AgentRequest,
        decision: RoutingDecision,
    ) -> bool:
        """Check if approval is required.
        
        Stub: Always requires approval for write operations.
        
        Args:
            request: The agent request
            decision: The routing decision
            
        Returns:
            True if approval is required
        """
        # Stub: Require approval for write-capable servers
        has_write = any(
            cap.action in ["write", "execute"]
            for cap in decision.server.capabilities
        )
        return has_write
    
    def request_approval(
        self,
        request: AgentRequest,
        decision: RoutingDecision,
    ) -> bool:
        """Request approval for a decision.
        
        Stub: Auto-approves all requests.
        
        Args:
            request: The agent request
            decision: The routing decision
            
        Returns:
            True (auto-approved)
        """
        logger.info(
            f"Approval requested for: {decision.server.name} "
            f"(intent: {request.intent})"
        )
        # Stub: Auto-approve
        return True


__all__ = [
    "MCPRouter",
    "MCPServerConfig",
    "MCPCapability",
    "AgentRequest",
    "RoutingDecision",
    "TransportType",
    "ApprovalPolicy",
    "DefaultApprovalPolicy",
]
