"""Embedded MCP Loader for local MCP servers within cugar-agent.

This module provides a loader for embedded MCP servers that are defined
inside the cugar-agent repository, with permission scope enforcement.

Features:
- Manifest-based server definitions
- Permission scope enforcement (read-only, read-write, etc.)
- Sandboxed execution within repository
- Dynamic discovery of available servers
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


class EmbeddedMCPLoader:
    """Loader for embedded MCP servers within the cugar-agent repository.
    
    This loader discovers and manages MCP servers that are embedded within
    the cugar-agent codebase, enforcing permission scopes as declared in
    their manifest files.
    
    Attributes:
        repo_root: Root directory of the cugar-agent repository
        manifest_file: Path to the manifest file defining embedded servers
        servers: Dictionary of loaded server definitions
    """

    def __init__(
        self,
        repo_root: Optional[Path] = None,
        manifest_file: str = "mcp_servers_manifest.yaml",
    ) -> None:
        """Initialize the Embedded MCP Loader.
        
        Args:
            repo_root: Root directory of the repository (default: auto-detect)
            manifest_file: Name of the manifest file (default: mcp_servers_manifest.yaml)
        """
        self.repo_root = repo_root or self._find_repo_root()
        self.manifest_file = self.repo_root / manifest_file
        self.servers: Dict[str, Dict[str, Any]] = {}
        
        logger.info(f"Initialized EmbeddedMCPLoader with repo root: {self.repo_root}")

    def _find_repo_root(self) -> Path:
        """Find the repository root by searching for .git directory.
        
        Returns:
            Path to the repository root
            
        Raises:
            RuntimeError: If repository root cannot be found
        """
        current = Path.cwd().resolve()
        
        while current != current.parent:
            if (current / ".git").exists():
                return current
            current = current.parent
        
        # Fallback to current working directory
        logger.warning("Could not find .git directory, using current directory as repo root")
        return Path.cwd().resolve()

    def load_manifest(self) -> Dict[str, Dict[str, Any]]:
        """Load the embedded servers manifest.
        
        Returns:
            Dictionary of server definitions keyed by server name
            
        Raises:
            FileNotFoundError: If manifest file does not exist
            ValueError: If manifest is invalid
        """
        if not self.manifest_file.exists():
            logger.warning(f"Manifest file not found: {self.manifest_file}")
            return {}
        
        try:
            with open(self.manifest_file, "r") as f:
                manifest_data = yaml.safe_load(f)
            
            if not manifest_data or "servers" not in manifest_data:
                logger.warning("Manifest file is empty or missing 'servers' key")
                return {}
            
            servers = manifest_data["servers"]
            
            # Validate and process server definitions
            for name, config in servers.items():
                if not self._validate_server_config(name, config):
                    logger.warning(f"Invalid server configuration for: {name}")
                    continue
                
                # Resolve paths relative to repo root
                if "path" in config:
                    config["path"] = str(self.repo_root / config["path"])
                
                self.servers[name] = config
            
            logger.info(f"Loaded {len(self.servers)} embedded servers from manifest")
            return self.servers
            
        except yaml.YAMLError as exc:
            logger.error(f"Failed to parse manifest file: {exc}")
            raise ValueError(f"Invalid YAML in manifest file: {exc}") from exc
        except Exception as exc:
            logger.error(f"Failed to load manifest: {exc}")
            raise

    def _validate_server_config(self, name: str, config: Dict[str, Any]) -> bool:
        """Validate a server configuration.
        
        Args:
            name: Server name
            config: Server configuration dictionary
            
        Returns:
            True if configuration is valid, False otherwise
        """
        required_fields = ["path", "permission_scope"]
        
        for field in required_fields:
            if field not in config:
                logger.warning(f"Server '{name}' missing required field: {field}")
                return False
        
        # Validate permission scope
        valid_scopes = ["read-only", "read-write", "execute", "admin"]
        scope = config.get("permission_scope")
        
        if scope not in valid_scopes:
            logger.warning(
                f"Server '{name}' has invalid permission_scope: {scope}. "
                f"Valid scopes: {valid_scopes}"
            )
            return False
        
        # Validate path exists
        server_path = self.repo_root / config["path"]
        if not server_path.exists():
            logger.warning(f"Server '{name}' path does not exist: {server_path}")
            return False
        
        return True

    def get_server(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a server definition by name.
        
        Args:
            name: Server name
            
        Returns:
            Server configuration dictionary or None if not found
        """
        if not self.servers:
            self.load_manifest()
        
        return self.servers.get(name)

    def list_servers(self) -> List[str]:
        """List all available embedded server names.
        
        Returns:
            List of server names
        """
        if not self.servers:
            self.load_manifest()
        
        return list(self.servers.keys())

    def get_server_capabilities(self, name: str) -> List[str]:
        """Get the capabilities of a server.
        
        Args:
            name: Server name
            
        Returns:
            List of capability strings
        """
        server = self.get_server(name)
        if not server:
            return []
        
        return server.get("capabilities", [])

    def check_permission(self, name: str, required_permission: str) -> bool:
        """Check if a server has the required permission level.
        
        Args:
            name: Server name
            required_permission: Required permission level
                (e.g., "read-only", "read-write", "execute", "admin")
            
        Returns:
            True if server has the required permission, False otherwise
        """
        server = self.get_server(name)
        if not server:
            return False
        
        # Define permission hierarchy
        permission_levels = {
            "read-only": 1,
            "read-write": 2,
            "execute": 3,
            "admin": 4,
        }
        
        server_scope = server.get("permission_scope", "read-only")
        server_level = permission_levels.get(server_scope, 0)
        required_level = permission_levels.get(required_permission, 0)
        
        return server_level >= required_level

    def load_server_module(self, name: str) -> Any:
        """Load a server module dynamically.
        
        Args:
            name: Server name
            
        Returns:
            Loaded server module
            
        Raises:
            ImportError: If module cannot be loaded
            ValueError: If server not found or invalid
        """
        server = self.get_server(name)
        if not server:
            raise ValueError(f"Server not found: {name}")
        
        server_path = Path(server["path"])
        
        # Ensure path is within repository (security check)
        try:
            server_path.resolve().relative_to(self.repo_root.resolve())
        except ValueError:
            raise ValueError(
                f"Server path is outside repository: {server_path}"
            )
        
        # Check permission scope before loading
        if not self.check_permission(name, "read-only"):
            raise PermissionError(
                f"Insufficient permissions to load server: {name}"
            )
        
        # Import the server module
        module_name = server.get("module")
        if not module_name:
            raise ValueError(f"Server '{name}' missing 'module' field in manifest")
        
        try:
            import importlib
            module = importlib.import_module(module_name)
            logger.info(f"Loaded embedded server module: {name} ({module_name})")
            return module
        except ImportError as exc:
            logger.error(f"Failed to import server module {module_name}: {exc}")
            raise

    def get_manifest_path(self) -> Path:
        """Get the path to the manifest file.
        
        Returns:
            Path to the manifest file
        """
        return self.manifest_file

    def create_example_manifest(self, output_path: Optional[Path] = None) -> None:
        """Create an example manifest file.
        
        Args:
            output_path: Optional custom output path (default: self.manifest_file)
        """
        output_path = output_path or self.manifest_file
        
        example_manifest = {
            "servers": {
                "example-filesystem": {
                    "path": "mcp_servers/filesystem",
                    "module": "cuga.mcp_servers.filesystem.server",
                    "permission_scope": "read-write",
                    "capabilities": [
                        "file.read",
                        "file.write",
                        "directory.list",
                    ],
                    "description": "Local filesystem operations",
                },
                "example-calculator": {
                    "path": "mcp_servers/calculator",
                    "module": "cuga.mcp_servers.calculator.server",
                    "permission_scope": "read-only",
                    "capabilities": [
                        "math.add",
                        "math.subtract",
                        "math.multiply",
                        "math.divide",
                    ],
                    "description": "Basic calculator operations",
                },
            }
        }
        
        with open(output_path, "w") as f:
            yaml.dump(example_manifest, f, default_flow_style=False, sort_keys=False)
        
        logger.info(f"Created example manifest at: {output_path}")
