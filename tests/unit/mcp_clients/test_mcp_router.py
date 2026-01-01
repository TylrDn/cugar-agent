"""Tests for MCP Router."""

import unittest
import os
import sys

# Set PYTHONPATH to include the root directory for absolute imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.mcp_router import (
    MCPRouter,
    MCPServerConfig,
    MCPCapability,
    AgentRequest,
    RoutingDecision,
    TransportType,
    DefaultApprovalPolicy,
)


class TestMCPRouter(unittest.TestCase):
    """Test cases for MCPRouter."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create test servers
        self.http_server = MCPServerConfig(
            name="http-test",
            transport=TransportType.HTTP,
            capabilities=[
                MCPCapability(action="read", auth="token-required"),
                MCPCapability(action="search", auth="token-required"),
            ],
            permission_scope="read-only",
        )
        
        self.process_server = MCPServerConfig(
            name="process-test",
            transport=TransportType.STDIO,
            capabilities=[
                MCPCapability(action="read", auth="none"),
                MCPCapability(action="write", auth="none"),
            ],
            permission_scope="read-write",
        )
        
        self.embedded_server = MCPServerConfig(
            name="embedded-test",
            transport=TransportType.EMBEDDED,
            capabilities=[
                MCPCapability(action="compute", auth="none"),
            ],
            permission_scope="read-only",
        )
        
        self.router = MCPRouter(
            servers=[self.http_server, self.process_server, self.embedded_server]
        )
    
    def test_initialization(self):
        """Test router initialization."""
        self.assertEqual(len(self.router.servers), 3)
        self.assertIsNone(self.router.approval_policy)
    
    def test_initialization_with_policy(self):
        """Test router initialization with approval policy."""
        policy = DefaultApprovalPolicy()
        router = MCPRouter(servers=[], approval_policy=policy)
        self.assertIsNotNone(router.approval_policy)
    
    def test_add_server(self):
        """Test adding a server to the router."""
        router = MCPRouter()
        self.assertEqual(len(router.servers), 0)
        
        router.add_server(self.http_server)
        self.assertEqual(len(router.servers), 1)
    
    def test_route_request_no_capabilities(self):
        """Test routing request without specific capabilities."""
        request = AgentRequest(
            intent="Test request",
            category="general",
        )
        
        decision = self.router.route_request(request)
        
        # Should return a server (first matching)
        self.assertIsNotNone(decision)
        self.assertIsInstance(decision, RoutingDecision)
    
    def test_route_request_with_capabilities(self):
        """Test routing request with specific capabilities."""
        request = AgentRequest(
            intent="Read data",
            category="data",
            required_capabilities=["read"],
        )
        
        decision = self.router.route_request(request)
        
        self.assertIsNotNone(decision)
        # Should match http_server or process_server
        self.assertIn(decision.server.name, ["http-test", "process-test"])
    
    def test_route_request_no_match(self):
        """Test routing request with no matching server."""
        request = AgentRequest(
            intent="Unsupported operation",
            category="special",
            required_capabilities=["unsupported-capability"],
        )
        
        decision = self.router.route_request(request)
        
        # Should return None (no matching server)
        self.assertIsNone(decision)
    
    def test_get_server_by_name(self):
        """Test getting server by name."""
        server = self.router.get_server_by_name("http-test")
        self.assertIsNotNone(server)
        self.assertEqual(server.name, "http-test")
        
        # Non-existent server
        server = self.router.get_server_by_name("nonexistent")
        self.assertIsNone(server)
    
    def test_list_servers(self):
        """Test listing all servers."""
        servers = self.router.list_servers()
        self.assertEqual(len(servers), 3)
    
    def test_get_servers_by_capability(self):
        """Test getting servers by capability."""
        servers = self.router.get_servers_by_capability("read")
        self.assertEqual(len(servers), 2)  # http-test and process-test
        
        servers = self.router.get_servers_by_capability("compute")
        self.assertEqual(len(servers), 1)  # embedded-test only
        
        servers = self.router.get_servers_by_capability("nonexistent")
        self.assertEqual(len(servers), 0)
    
    def test_get_servers_by_transport(self):
        """Test getting servers by transport type."""
        servers = self.router.get_servers_by_transport(TransportType.HTTP)
        self.assertEqual(len(servers), 1)
        self.assertEqual(servers[0].name, "http-test")
        
        servers = self.router.get_servers_by_transport(TransportType.STDIO)
        self.assertEqual(len(servers), 1)
        self.assertEqual(servers[0].name, "process-test")


class TestDefaultApprovalPolicy(unittest.TestCase):
    """Test cases for DefaultApprovalPolicy."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.policy = DefaultApprovalPolicy()
    
    def test_requires_approval_read_only(self):
        """Test approval requirement for read-only operations."""
        server = MCPServerConfig(
            name="test",
            transport=TransportType.HTTP,
            capabilities=[MCPCapability(action="read")],
        )
        
        request = AgentRequest(intent="Read data")
        decision = RoutingDecision(server=server, reason="test")
        
        requires = self.policy.requires_approval(request, decision)
        self.assertFalse(requires)
    
    def test_requires_approval_write(self):
        """Test approval requirement for write operations."""
        server = MCPServerConfig(
            name="test",
            transport=TransportType.HTTP,
            capabilities=[MCPCapability(action="write")],
        )
        
        request = AgentRequest(intent="Write data")
        decision = RoutingDecision(server=server, reason="test")
        
        requires = self.policy.requires_approval(request, decision)
        self.assertTrue(requires)
    
    def test_request_approval(self):
        """Test requesting approval."""
        server = MCPServerConfig(
            name="test",
            transport=TransportType.HTTP,
            capabilities=[MCPCapability(action="write")],
        )
        
        request = AgentRequest(intent="Write data")
        decision = RoutingDecision(server=server, reason="test")
        
        # Auto-approves in stub implementation
        approved = self.policy.request_approval(request, decision)
        self.assertTrue(approved)


class TestMCPCapability(unittest.TestCase):
    """Test cases for MCPCapability."""
    
    def test_initialization(self):
        """Test capability initialization."""
        cap = MCPCapability(action="read")
        self.assertEqual(cap.action, "read")
        self.assertEqual(cap.auth, "none")
        self.assertEqual(cap.description, "")
    
    def test_initialization_with_auth(self):
        """Test capability initialization with auth."""
        cap = MCPCapability(
            action="write",
            auth="token-required",
            description="Write data",
        )
        self.assertEqual(cap.action, "write")
        self.assertEqual(cap.auth, "token-required")
        self.assertEqual(cap.description, "Write data")


class TestAgentRequest(unittest.TestCase):
    """Test cases for AgentRequest."""
    
    def test_initialization(self):
        """Test request initialization."""
        request = AgentRequest(intent="Test intent")
        self.assertEqual(request.intent, "Test intent")
        self.assertEqual(request.category, "general")
        self.assertEqual(len(request.required_capabilities), 0)
        self.assertEqual(len(request.context), 0)
    
    def test_initialization_with_capabilities(self):
        """Test request initialization with capabilities."""
        request = AgentRequest(
            intent="Test intent",
            category="data",
            required_capabilities=["read", "write"],
            context={"user_id": "123"},
        )
        self.assertEqual(request.category, "data")
        self.assertEqual(len(request.required_capabilities), 2)
        self.assertIn("read", request.required_capabilities)
        self.assertEqual(request.context["user_id"], "123")


if __name__ == '__main__':
    unittest.main()
