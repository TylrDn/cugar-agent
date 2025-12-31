"""MCP registry loader with deny-by-default and manifest resolution.

This module implements the core registry loading functionality for MCP tools,
enforcing a deny-by-default policy for unregistered tools and providing
stable, deterministic tool resolution.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MCPRegistryError(Exception):
    """Base exception for MCP registry errors."""
    pass


class UnregisteredToolError(MCPRegistryError):
    """Raised when attempting to access an unregistered tool."""
    pass


class MCPToolManifest:
    """Represents a single MCP tool entry from the registry."""
    
    def __init__(
        self,
        tool_id: str,
        tier: int,
        enabled: bool,
        protocol: str,
        ref: str,
        sandbox: str,
        scopes: List[str],
        env: Dict[str, str],
        mounts: List[str],
        budget_policy: str,
    ):
        self.id = tool_id
        self.tier = tier
        self.enabled = enabled
        self.protocol = protocol
        self.ref = ref
        self.sandbox = sandbox
        self.scopes = scopes
        self.env = env
        self.mounts = mounts
        self.budget_policy = budget_policy
    
    def __repr__(self) -> str:
        return f"MCPToolManifest(id={self.id!r}, tier={self.tier}, enabled={self.enabled})"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert manifest to dictionary representation."""
        return {
            "id": self.id,
            "tier": self.tier,
            "enabled": self.enabled,
            "protocol": self.protocol,
            "ref": self.ref,
            "sandbox": self.sandbox,
            "scopes": self.scopes,
            "env": self.env,
            "mounts": self.mounts,
            "budget_policy": self.budget_policy,
        }


class MCPRegistryLoader:
    """Loads and validates MCP tool registry with deny-by-default policy.
    
    This loader enforces strict access control:
    - Only tools explicitly registered in the registry are accessible
    - Tier filtering allows controlling which tool categories are available
    - Stable sorting ensures deterministic tool resolution
    - Validation ensures all required fields are present
    """
    
    def __init__(
        self,
        registry_path: Optional[Path] = None,
        allowed_tiers: Optional[List[int]] = None,
    ):
        """Initialize the MCP registry loader.
        
        Args:
            registry_path: Path to the registry YAML file.
                          Defaults to docs/mcp/registry.yaml
            allowed_tiers: List of allowed tier levels. If None, all tiers are allowed.
                          Tier 1 is default-on, Tier 2 is opt-in.
        """
        self.registry_path = registry_path or self._default_registry_path()
        self.allowed_tiers = allowed_tiers
        self._manifests: Dict[str, MCPToolManifest] = {}
        self._loaded = False
    
    @staticmethod
    def _default_registry_path() -> Path:
        """Get the default registry path."""
        # Try to find the registry relative to this file
        current = Path(__file__).parent
        for _ in range(5):  # Search up to 5 levels
            candidate = current / "docs" / "mcp" / "registry.yaml"
            if candidate.exists():
                return candidate
            current = current.parent
        # Fallback to a predictable location
        return Path.cwd() / "docs" / "mcp" / "registry.yaml"
    
    def load(self) -> None:
        """Load the registry from the YAML file."""
        if self._loaded:
            return
        
        if not self.registry_path.exists():
            logger.warning(f"Registry file not found: {self.registry_path}")
            self._loaded = True
            return
        
        try:
            import yaml
        except ImportError:
            logger.error("PyYAML is required to load registry")
            raise MCPRegistryError("PyYAML not installed")
        
        with open(self.registry_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        if not isinstance(data, dict):
            raise MCPRegistryError(f"Invalid registry format: expected dict, got {type(data)}")
        
        # Extract defaults
        defaults = data.get("defaults", {})
        default_tier = defaults.get("tier", 1)
        default_enabled = defaults.get("enabled", True)
        default_protocol = defaults.get("protocol", "mcp")
        default_sandbox = defaults.get("sandbox", "py-slim")
        default_scopes = defaults.get("scopes", [])
        default_env = defaults.get("env", {})
        default_mounts = defaults.get("mounts", [])
        default_budget_policy = defaults.get("budget_policy", "warn")
        
        # Load entries
        entries = data.get("entries", [])
        if not isinstance(entries, list):
            raise MCPRegistryError(f"Invalid entries format: expected list, got {type(entries)}")
        
        manifests = []
        for entry in entries:
            if not isinstance(entry, dict):
                logger.warning(f"Skipping invalid entry: {entry}")
                continue
            
            tool_id = entry.get("id")
            if not tool_id:
                logger.warning("Skipping entry without id")
                continue
            
            # Apply defaults
            tier = entry.get("tier", default_tier)
            enabled = entry.get("enabled", default_enabled)
            protocol = entry.get("protocol", default_protocol)
            ref = entry.get("ref", "")
            sandbox = entry.get("sandbox", default_sandbox)
            scopes = entry.get("scopes", default_scopes)
            env = {**default_env, **entry.get("env", {})}
            mounts = entry.get("mounts", default_mounts)
            budget_policy = entry.get("budget_policy", default_budget_policy)
            
            # Filter by tier if specified
            if self.allowed_tiers is not None and tier not in self.allowed_tiers:
                logger.debug(f"Skipping tool {tool_id} (tier {tier} not in allowed tiers)")
                continue
            
            # Skip disabled tools
            if not enabled:
                logger.debug(f"Skipping disabled tool {tool_id}")
                continue
            
            manifest = MCPToolManifest(
                tool_id=tool_id,
                tier=tier,
                enabled=enabled,
                protocol=protocol,
                ref=ref,
                sandbox=sandbox,
                scopes=scopes,
                env=env,
                mounts=mounts,
                budget_policy=budget_policy,
            )
            manifests.append(manifest)
        
        # Sort manifests by id for stable ordering
        manifests.sort(key=lambda m: m.id)
        
        # Store in dictionary for fast lookup
        self._manifests = {m.id: m for m in manifests}
        self._loaded = True
        
        logger.info(f"Loaded {len(self._manifests)} tools from registry")
    
    def get_manifest(self, tool_id: str) -> MCPToolManifest:
        """Get a tool manifest by ID.
        
        Args:
            tool_id: The tool identifier
            
        Returns:
            The tool manifest
            
        Raises:
            UnregisteredToolError: If the tool is not registered
        """
        if not self._loaded:
            self.load()
        
        manifest = self._manifests.get(tool_id)
        if manifest is None:
            raise UnregisteredToolError(
                f"Tool '{tool_id}' is not registered. "
                f"Available tools: {sorted(self._manifests.keys())}"
            )
        
        return manifest
    
    def list_manifests(self) -> List[MCPToolManifest]:
        """List all registered tool manifests in stable order.
        
        Returns:
            List of tool manifests sorted by ID
        """
        if not self._loaded:
            self.load()
        
        # Return sorted list for deterministic ordering
        return sorted(self._manifests.values(), key=lambda m: m.id)
    
    def has_tool(self, tool_id: str) -> bool:
        """Check if a tool is registered.
        
        Args:
            tool_id: The tool identifier
            
        Returns:
            True if the tool is registered and enabled
        """
        if not self._loaded:
            self.load()
        
        return tool_id in self._manifests
    
    def get_tools_by_tier(self, tier: int) -> List[MCPToolManifest]:
        """Get all tools for a specific tier.
        
        Args:
            tier: The tier level (1 for default-on, 2 for opt-in)
            
        Returns:
            List of tool manifests for the specified tier
        """
        if not self._loaded:
            self.load()
        
        return sorted(
            [m for m in self._manifests.values() if m.tier == tier],
            key=lambda m: m.id
        )
    
    def get_tools_by_scope(self, scope: str) -> List[MCPToolManifest]:
        """Get all tools that include a specific scope.
        
        Args:
            scope: The scope to filter by (e.g., 'fs', 'exec', 'web')
            
        Returns:
            List of tool manifests that include the scope
        """
        if not self._loaded:
            self.load()
        
        return sorted(
            [m for m in self._manifests.values() if scope in m.scopes],
            key=lambda m: m.id
        )


def load_mcp_registry(
    registry_path: Optional[Path] = None,
    allowed_tiers: Optional[List[int]] = None,
) -> MCPRegistryLoader:
    """Convenience function to create and load an MCP registry.
    
    Args:
        registry_path: Path to the registry YAML file
        allowed_tiers: List of allowed tier levels
        
    Returns:
        Loaded MCPRegistryLoader instance
    """
    loader = MCPRegistryLoader(registry_path, allowed_tiers)
    loader.load()
    return loader
