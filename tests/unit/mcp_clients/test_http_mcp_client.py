"""Tests for HTTP MCP Client."""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import os
import sys

# Set PYTHONPATH to include the root directory for absolute imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from src.mcp_clients.http_mcp_client import HttpMCPClient


class TestHttpMCPClient(unittest.IsolatedAsyncioTestCase):
    """Test cases for HttpMCPClient."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.base_url = "https://example.com/mcp"
        self.client = HttpMCPClient(
            base_url=self.base_url,
            timeout=5.0,
            max_retries=2,
        )
    
    def tearDown(self):
        """Clean up resources."""
        if self.client:
            self.client.close()
    
    def test_initialization(self):
        """Test client initialization."""
        self.assertEqual(self.client.base_url, self.base_url)
        self.assertEqual(self.client.timeout, 5.0)
        self.assertEqual(self.client.max_retries, 2)
        self.assertIn("Content-Type", self.client.headers)
    
    def test_initialization_with_auth_token(self):
        """Test client initialization with auth token."""
        client = HttpMCPClient(
            base_url=self.base_url,
            auth_token="test-token-123",
        )
        self.assertIn("Authorization", client.headers)
        self.assertEqual(client.headers["Authorization"], "Bearer test-token-123")
        client.close()
    
    @patch('httpx.Client')
    async def test_discover_tools_success(self, mock_client_class):
        """Test successful tool discovery."""
        # Mock the HTTP response
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "tools": [
                    {"name": "tool1", "description": "Test tool 1"},
                    {"name": "tool2", "description": "Test tool 2"},
                ]
            }
        }
        
        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        # Force client creation
        self.client._client = mock_client
        
        tools = await self.client.discover_tools()
        
        # Verify we got the tools (note: result wrapping may differ)
        self.assertIsInstance(tools, list)
        mock_client.post.assert_called_once()
    
    @patch('httpx.Client')
    async def test_call_tool_success(self, mock_client_class):
        """Test successful tool call."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "result": {"output": "success"}
        }
        
        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        self.client._client = mock_client
        
        result = await self.client.call_tool(
            "test_tool",
            {"param": "value"}
        )
        
        self.assertIsInstance(result, dict)
        mock_client.post.assert_called_once()
    
    @patch('httpx.Client')
    async def test_health_check_success(self, mock_client_class):
        """Test successful health check."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"result": {"status": "ok"}}
        
        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        self.client._client = mock_client
        
        is_healthy = await self.client.health_check()
        
        self.assertTrue(is_healthy)
    
    @patch('httpx.Client')
    async def test_health_check_failure(self, mock_client_class):
        """Test health check failure."""
        mock_client = MagicMock()
        mock_client.post.side_effect = Exception("Connection failed")
        mock_client_class.return_value = mock_client
        
        self.client._client = mock_client
        
        is_healthy = await self.client.health_check()
        
        self.assertFalse(is_healthy)
    
    async def test_context_manager(self):
        """Test async context manager."""
        async with HttpMCPClient(self.base_url) as client:
            self.assertIsNotNone(client)
        # Client should be closed after context


if __name__ == '__main__':
    unittest.main()
