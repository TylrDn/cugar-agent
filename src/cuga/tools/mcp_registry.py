"""MCP Registry loader with tier-based security enforcement and deterministic behavior."""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

logger = logging.getLogger(__name__)


TierLevel = Literal["sandbox", "restricted", "trusted"]
TierNumber = Literal[1, 2, 3]


@dataclass
class MCPToolEntry:
    """Represents a single MCP tool entry with tier and security constraints."""

    id: str
    tier: int = 1
    enabled: bool = True
    protocol: str = "mcp"
    sandbox: str = "py-slim"
    scopes: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    mounts: List[str] = field(default_factory=list)
    ref: Optional[str] = None
    budget_policy: str = "warn"
    description: Optional[str] = None
    constraints: Dict[str, Any] = field(default_factory=dict)

    def get_tier_name(self) -> TierLevel:
        """Convert tier number to tier name."""
        tier_map = {1: "sandbox", 2: "restricted", 3: "trusted"}
        return tier_map.get(self.tier, "sandbox")  # type: ignore

    def is_allowed(self, requested_tier: Optional[int] = None) -> bool:
        """Check if tool is allowed based on enabled flag and requested tier."""
        if not self.enabled:
            return False
        if requested_tier is not None:
            return self.tier <= requested_tier
        return True


@dataclass
class MCPRegistryManifest:
    """Manifest containing all MCP tools with tier-based access control."""

    version: str = "v1"
    defaults: Dict[str, Any] = field(default_factory=dict)
    entries: List[MCPToolEntry] = field(default_factory=list)

    def get_tool(self, tool_id: str) -> Optional[MCPToolEntry]:
        """Get a specific tool by ID."""
        for entry in self.entries:
            if entry.id == tool_id:
                return entry
        return None

    def list_tools(
        self, tier: Optional[int] = None, enabled_only: bool = True, sorted_by_id: bool = True
    ) -> List[MCPToolEntry]:
        """List tools with optional filtering and deterministic sorting."""
        tools = [
            entry
            for entry in self.entries
            if (not enabled_only or entry.enabled) and (tier is None or entry.tier <= tier)
        ]
        if sorted_by_id:
            tools = sorted(tools, key=lambda t: t.id)
        return tools

    def get_tier_counts(self) -> Dict[int, int]:
        """Get count of tools per tier."""
        counts: Dict[int, int] = {}
        for entry in self.entries:
            counts[entry.tier] = counts.get(entry.tier, 0) + 1
        return dict(sorted(counts.items()))


class MCPRegistryLoader:
    """Loads and validates MCP registry with deny-by-default security."""

    def __init__(
        self,
        registry_path: Optional[Path] = None,
        deny_by_default: bool = True,
        validate_refs: bool = False,
    ):
        """
        Initialize the registry loader.

        Args:
            registry_path: Path to registry.yaml file. Defaults to docs/mcp/registry.yaml
            deny_by_default: If True, only explicitly enabled tools are loaded
            validate_refs: If True, validate tool references (docker://, http://, etc.)
        """
        self.deny_by_default = deny_by_default
        self.validate_refs = validate_refs

        if registry_path is None:
            # Default to docs/mcp/registry.yaml relative to project root
            project_root = Path(__file__).parent.parent.parent.parent
            registry_path = project_root / "docs" / "mcp" / "registry.yaml"

        self.registry_path = registry_path
        self._manifest: Optional[MCPRegistryManifest] = None

    def load(self) -> MCPRegistryManifest:
        """Load registry from YAML file with validation."""
        if not self.registry_path.exists():
            logger.warning(f"Registry file not found: {self.registry_path}")
            return MCPRegistryManifest()

        try:
            yaml = self._import_yaml()
            with open(self.registry_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            manifest = self._parse_manifest(data)
            self._validate_manifest(manifest)
            self._manifest = manifest
            return manifest

        except Exception as e:
            logger.error(f"Failed to load registry: {e}")
            raise RuntimeError(f"Registry load failed: {e}") from e

    def _import_yaml(self) -> Any:
        """Import PyYAML with fallback error."""
        yaml_spec = importlib.util.find_spec("yaml")
        if yaml_spec is None:
            raise ImportError("PyYAML is required but not installed")
        return importlib.import_module("yaml")

    def _parse_manifest(self, data: Dict[str, Any]) -> MCPRegistryManifest:
        """Parse raw YAML data into manifest structure."""
        manifest = MCPRegistryManifest(
            version=data.get("version", "v1"), defaults=data.get("defaults", {})
        )

        entries_data = data.get("entries", [])
        defaults = manifest.defaults

        for entry_data in entries_data:
            # Apply defaults
            entry = MCPToolEntry(
                id=entry_data["id"],
                tier=entry_data.get("tier", defaults.get("tier", 1)),
                enabled=entry_data.get("enabled", defaults.get("enabled", True)),
                protocol=entry_data.get("protocol", defaults.get("protocol", "mcp")),
                sandbox=entry_data.get("sandbox", defaults.get("sandbox", "py-slim")),
                scopes=entry_data.get("scopes", defaults.get("scopes", [])),
                env=entry_data.get("env", {}),
                mounts=entry_data.get("mounts", defaults.get("mounts", [])),
                ref=entry_data.get("ref"),
                budget_policy=entry_data.get(
                    "budget_policy", defaults.get("budget_policy", "warn")
                ),
                description=entry_data.get("description"),
                constraints=entry_data.get("constraints", {}),
            )

            # Deny-by-default: only add if explicitly enabled or deny_by_default is False
            if not self.deny_by_default or entry.enabled:
                manifest.entries.append(entry)

        # Ensure deterministic ordering
        manifest.entries = sorted(manifest.entries, key=lambda e: e.id)

        return manifest

    def _validate_manifest(self, manifest: MCPRegistryManifest) -> None:
        """Validate manifest for consistency and security."""
        # Check for duplicate IDs
        ids = [e.id for e in manifest.entries]
        if len(ids) != len(set(ids)):
            duplicates = [id for id in ids if ids.count(id) > 1]
            raise ValueError(f"Duplicate tool IDs found: {set(duplicates)}")

        # Validate tiers
        for entry in manifest.entries:
            if entry.tier not in [1, 2, 3]:
                logger.warning(f"Invalid tier {entry.tier} for tool {entry.id}, defaulting to 1")
                entry.tier = 1

        # Validate refs if requested
        if self.validate_refs:
            for entry in manifest.entries:
                if entry.ref and not self._is_valid_ref(entry.ref):
                    raise ValueError(f"Invalid ref for tool {entry.id}: {entry.ref}")

    def _is_valid_ref(self, ref: str) -> bool:
        """Validate tool reference format."""
        valid_protocols = ["docker://", "http://", "https://", "stdio://"]
        return any(ref.startswith(proto) for proto in valid_protocols) or ref.startswith("${")

    def get_manifest(self) -> Optional[MCPRegistryManifest]:
        """Get cached manifest without reloading."""
        return self._manifest

    def reload(self) -> MCPRegistryManifest:
        """Force reload of registry from disk."""
        self._manifest = None
        return self.load()


# Global registry instance (lazy loaded)
_global_registry: Optional[MCPRegistryLoader] = None


def get_registry(registry_path: Optional[Path] = None) -> MCPRegistryLoader:
    """Get or create the global registry instance."""
    global _global_registry
    if _global_registry is None:
        _global_registry = MCPRegistryLoader(registry_path=registry_path)
    return _global_registry


def load_mcp_manifest(registry_path: Optional[Path] = None) -> MCPRegistryManifest:
    """Load the MCP manifest from registry file."""
    registry = get_registry(registry_path)
    return registry.load()
