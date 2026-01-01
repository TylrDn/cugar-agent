"""Tests for Process MCP Client."""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio
import os
import sys

# Set PYTHONPATH to include the root directory for absolute imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from src.mcp_clients.process_mcp_client import ProcessMCPClient


class TestProcessMCPClient(unittest.IsolatedAsyncioTestCase):
    """Test cases for ProcessMCPClient."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.command = "python"
        self.args = ["-m", "test_server"]
        self.client = ProcessMCPClient(
            command=self.command,
            args=self.args,
            timeout=5.0,
            max_restarts=2,
        )
    
    async def asyncTearDown(self):
        """Clean up resources."""
        if self.client and self.client.process:
            await self.client.stop()
    
    def test_initialization(self):
        """Test client initialization."""
        self.assertEqual(self.client.command, self.command)
        self.assertEqual(self.client.args, self.args)
        self.assertEqual(self.client.timeout, 5.0)
        self.assertEqual(self.client.max_restarts, 2)
        self.assertIsNone(self.client.process)
    
    @patch('asyncio.create_subprocess_exec')
    async def test_start_success(self, mock_create_subprocess):
        """Test successful process start."""
        # Mock process
        mock_process = AsyncMock()
        mock_process.returncode = None
        mock_process.stdin = AsyncMock()
        mock_process.stdout = AsyncMock()
        mock_process.stderr = AsyncMock()
        
        # Mock initialization response
        init_response = b'{"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2024-11-05"}}\n'
        mock_process.stdout.readline = AsyncMock(return_value=init_response)
        
        mock_create_subprocess.return_value = mock_process
        
        await self.client.start()
        
        self.assertIsNotNone(self.client.process)
        self.assertTrue(self.client._ready)
        mock_create_subprocess.assert_called_once()
    
    @patch('asyncio.create_subprocess_exec')
    async def test_start_command_not_found(self, mock_create_subprocess):
        """Test start with non-existent command."""
        mock_create_subprocess.side_effect = FileNotFoundError("Command not found")
        
        with self.assertRaises(RuntimeError):
            await self.client.start()
    
    @patch('asyncio.create_subprocess_exec')
    async def test_stop(self, mock_create_subprocess):
        """Test process stop."""
        # Mock process
        mock_process = AsyncMock()
        mock_process.returncode = None
        mock_process.stdin = AsyncMock()
        mock_process.stdout = AsyncMock()
        mock_process.stderr = AsyncMock()
        mock_process.send_signal = MagicMock()
        mock_process.wait = AsyncMock()
        
        # Mock initialization response
        init_response = b'{"jsonrpc": "2.0", "id": 1, "result": {}}\n'
        mock_process.stdout.readline = AsyncMock(return_value=init_response)
        
        mock_create_subprocess.return_value = mock_process
        
        await self.client.start()
        await self.client.stop()
        
        self.assertIsNone(self.client.process)
        self.assertFalse(self.client._ready)
    
    def test_is_healthy_no_process(self):
        """Test health check with no process."""
        self.assertFalse(self.client.is_healthy())
    
    @patch('asyncio.create_subprocess_exec')
    async def test_is_healthy_with_process(self, mock_create_subprocess):
        """Test health check with running process."""
        # Mock process
        mock_process = AsyncMock()
        mock_process.returncode = None
        mock_process.stdin = AsyncMock()
        mock_process.stdout = AsyncMock()
        
        # Mock initialization
        init_response = b'{"jsonrpc": "2.0", "id": 1, "result": {}}\n'
        mock_process.stdout.readline = AsyncMock(return_value=init_response)
        
        mock_create_subprocess.return_value = mock_process
        
        await self.client.start()
        
        self.assertTrue(self.client.is_healthy())
    
    @patch('asyncio.create_subprocess_exec')
    async def test_context_manager(self, mock_create_subprocess):
        """Test async context manager."""
        # Mock process
        mock_process = AsyncMock()
        mock_process.returncode = None
        mock_process.stdin = AsyncMock()
        mock_process.stdout = AsyncMock()
        mock_process.send_signal = MagicMock()
        mock_process.wait = AsyncMock()
        
        # Mock initialization
        init_response = b'{"jsonrpc": "2.0", "id": 1, "result": {}}\n'
        mock_process.stdout.readline = AsyncMock(return_value=init_response)
        
        mock_create_subprocess.return_value = mock_process
        
        async with ProcessMCPClient(self.command, self.args) as client:
            self.assertIsNotNone(client.process)
        
        # Process should be stopped after context
    
    def test_get_request_id(self):
        """Test request ID generation."""
        id1 = self.client._get_request_id()
        id2 = self.client._get_request_id()
        self.assertEqual(id1, 1)
        self.assertEqual(id2, 2)
        self.assertNotEqual(id1, id2)


if __name__ == '__main__':
    unittest.main()
