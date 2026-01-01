"""Tests for Embedded MCP Loader."""

import unittest
from unittest.mock import MagicMock, patch
import os
import sys
from pathlib import Path
import tempfile
import yaml

# Set PYTHONPATH to include the root directory for absolute imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from src.mcp_clients.embedded_mcp_loader import EmbeddedMCPLoader


class TestEmbeddedMCPLoader(unittest.TestCase):
    """Test cases for EmbeddedMCPLoader."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        self.repo_root = Path(self.temp_dir)
        
        # Create a test manifest
        self.manifest_file = "test_manifest.yaml"
        self.loader = EmbeddedMCPLoader(
            repo_root=self.repo_root,
            manifest_file=self.manifest_file,
        )
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_initialization(self):
        """Test loader initialization."""
        self.assertEqual(self.loader.repo_root, self.repo_root)
        self.assertEqual(self.loader.manifest_file, self.repo_root / self.manifest_file)
        self.assertIsInstance(self.loader.servers, dict)
    
    def test_find_repo_root(self):
        """Test repository root detection."""
        # Create a .git directory
        git_dir = self.repo_root / ".git"
        git_dir.mkdir()
        
        # Create a new loader without specifying repo_root
        with patch('pathlib.Path.cwd', return_value=self.repo_root):
            loader = EmbeddedMCPLoader(manifest_file=self.manifest_file)
            # Since we're in a temp dir without .git, it should use cwd
            self.assertIsNotNone(loader.repo_root)
    
    def test_load_manifest_file_not_found(self):
        """Test loading manifest when file doesn't exist."""
        servers = self.loader.load_manifest()
        self.assertEqual(servers, {})
    
    def test_load_manifest_success(self):
        """Test successful manifest loading."""
        # Create a valid manifest file
        manifest_data = {
            "servers": {
                "test-server": {
                    "path": "test_server",
                    "module": "test.module",
                    "permission_scope": "read-only",
                    "capabilities": ["test.read"],
                }
            }
        }
        
        # Create the server directory
        server_dir = self.repo_root / "test_server"
        server_dir.mkdir()
        
        manifest_path = self.repo_root / self.manifest_file
        with open(manifest_path, "w") as f:
            yaml.dump(manifest_data, f)
        
        servers = self.loader.load_manifest()
        
        self.assertIn("test-server", servers)
        self.assertEqual(servers["test-server"]["permission_scope"], "read-only")
    
    def test_validate_server_config_missing_field(self):
        """Test validation with missing required field."""
        config = {
            "path": "test_server",
            # Missing permission_scope
        }
        
        is_valid = self.loader._validate_server_config("test", config)
        self.assertFalse(is_valid)
    
    def test_validate_server_config_invalid_scope(self):
        """Test validation with invalid permission scope."""
        config = {
            "path": "test_server",
            "permission_scope": "invalid-scope",
        }
        
        is_valid = self.loader._validate_server_config("test", config)
        self.assertFalse(is_valid)
    
    def test_validate_server_config_path_not_exists(self):
        """Test validation with non-existent path."""
        config = {
            "path": "nonexistent_server",
            "permission_scope": "read-only",
        }
        
        is_valid = self.loader._validate_server_config("test", config)
        self.assertFalse(is_valid)
    
    def test_get_server(self):
        """Test getting a server by name."""
        # Add a server manually
        self.loader.servers = {
            "test-server": {
                "path": "test_server",
                "permission_scope": "read-only",
            }
        }
        
        server = self.loader.get_server("test-server")
        self.assertIsNotNone(server)
        self.assertEqual(server["permission_scope"], "read-only")
        
        # Non-existent server
        server = self.loader.get_server("nonexistent")
        self.assertIsNone(server)
    
    def test_list_servers(self):
        """Test listing all servers."""
        self.loader.servers = {
            "server1": {"path": "path1"},
            "server2": {"path": "path2"},
        }
        
        servers = self.loader.list_servers()
        self.assertEqual(len(servers), 2)
        self.assertIn("server1", servers)
        self.assertIn("server2", servers)
    
    def test_get_server_capabilities(self):
        """Test getting server capabilities."""
        self.loader.servers = {
            "test-server": {
                "capabilities": ["read", "write", "execute"],
            }
        }
        
        capabilities = self.loader.get_server_capabilities("test-server")
        self.assertEqual(len(capabilities), 3)
        self.assertIn("read", capabilities)
    
    def test_check_permission(self):
        """Test permission checking."""
        self.loader.servers = {
            "read-server": {"permission_scope": "read-only"},
            "write-server": {"permission_scope": "read-write"},
            "exec-server": {"permission_scope": "execute"},
        }
        
        # Read-only server
        self.assertTrue(self.loader.check_permission("read-server", "read-only"))
        self.assertFalse(self.loader.check_permission("read-server", "read-write"))
        
        # Read-write server
        self.assertTrue(self.loader.check_permission("write-server", "read-only"))
        self.assertTrue(self.loader.check_permission("write-server", "read-write"))
        self.assertFalse(self.loader.check_permission("write-server", "execute"))
        
        # Execute server
        self.assertTrue(self.loader.check_permission("exec-server", "read-only"))
        self.assertTrue(self.loader.check_permission("exec-server", "read-write"))
        self.assertTrue(self.loader.check_permission("exec-server", "execute"))
    
    def test_get_manifest_path(self):
        """Test getting manifest path."""
        path = self.loader.get_manifest_path()
        self.assertEqual(path, self.repo_root / self.manifest_file)
    
    def test_create_example_manifest(self):
        """Test creating an example manifest."""
        output_path = self.repo_root / "example_manifest.yaml"
        self.loader.create_example_manifest(output_path)
        
        self.assertTrue(output_path.exists())
        
        # Verify it's valid YAML
        with open(output_path, "r") as f:
            data = yaml.safe_load(f)
        
        self.assertIn("servers", data)
        self.assertIn("example-filesystem", data["servers"])


if __name__ == '__main__':
    unittest.main()
