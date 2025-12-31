"""Tests for deterministic behavior across MCP operations."""

import json
from pathlib import Path

import pytest

from cuga.observability.mcp_audit import normalize_output
from cuga.tools.mcp_registry import MCPRegistryLoader
from cuga.tools.mcp_toolbox import create_mcp_toolbox


class TestDeterministicToolLoading:
    """Test deterministic tool loading behavior."""

    def test_repeated_loads_same_order(self, tmp_path):
        """Test that repeated loads produce the same tool order."""
        import yaml
        
        registry_path = tmp_path / "registry.yaml"
        with open(registry_path, "w") as f:
            yaml.safe_dump({
                "version": "v1",
                "entries": [
                    {"id": "z", "tier": 1, "enabled": True},
                    {"id": "a", "tier": 1, "enabled": True},
                    {"id": "m", "tier": 1, "enabled": True},
                ],
            }, f)
        
        # Load multiple times
        results = []
        for _ in range(5):
            toolbox = create_mcp_toolbox(
                allowed_tiers=[1],
                registry_path=registry_path,
            )
            results.append(toolbox.list_tool_ids())
        
        # All results should be identical
        first_result = results[0]
        for result in results[1:]:
            assert result == first_result
        
        # Should be sorted
        assert first_result == sorted(first_result)

    def test_fixture_normalization(self):
        """Test that fixture data is normalized correctly."""
        fixture_path = Path(__file__).parent / "data" / "mcp_deterministic" / "github_response.json"
        
        if not fixture_path.exists():
            pytest.skip("Fixture file not found")
        
        with open(fixture_path) as f:
            data = json.load(f)
        
        # Normalize the output
        normalized = normalize_output(data)
        
        # Timestamps should be removed
        assert "last_updated" not in normalized
        
        # Other fields should be present and sorted
        assert "repository" in normalized
        assert "branches" in normalized


class TestToolOutputNormalization:
    """Test output normalization for deterministic comparisons."""

    def test_normalize_removes_timestamps(self):
        """Test that timestamps are removed during normalization."""
        output = {
            "result": "success",
            "timestamp": "2024-01-15T10:00:00Z",
            "created_at": "2024-01-15T09:00:00Z",
            "data": "important"
        }
        
        normalized = normalize_output(output)
        
        assert "timestamp" not in normalized
        assert "created_at" not in normalized
        assert "result" in normalized
        assert "data" in normalized

    def test_normalize_sorts_dict_keys(self):
        """Test that dictionary keys are sorted."""
        output = {"z": 1, "a": 2, "m": 3}
        normalized = normalize_output(output)
        
        keys = list(normalized.keys())
        assert keys == ["a", "m", "z"]

    def test_normalize_nested_structures(self):
        """Test normalization of nested structures."""
        output = {
            "outer": {
                "z": 1,
                "a": 2,
                "timestamp": "2024-01-15"
            },
            "timestamp": "2024-01-15"
        }
        
        normalized = normalize_output(output)
        
        assert "timestamp" not in normalized
        assert "timestamp" not in normalized["outer"]
        assert list(normalized["outer"].keys()) == ["a", "z"]


class TestRegistryStability:
    """Test registry loading stability."""

    def test_registry_load_consistency(self, tmp_path):
        """Test that registry loads produce consistent results."""
        import yaml
        
        registry_path = tmp_path / "registry.yaml"
        with open(registry_path, "w") as f:
            yaml.safe_dump({
                "version": "v1",
                "entries": [
                    {"id": "tool3", "tier": 1, "enabled": True},
                    {"id": "tool1", "tier": 1, "enabled": True},
                    {"id": "tool2", "tier": 1, "enabled": True},
                ],
            }, f)
        
        # Load multiple times
        loaders = [
            MCPRegistryLoader(registry_path=registry_path, deny_by_default=False)
            for _ in range(3)
        ]
        manifests = [loader.load() for loader in loaders]
        
        # All manifests should have the same entries in the same order
        ids_lists = [[e.id for e in m.entries] for m in manifests]
        
        first_ids = ids_lists[0]
        for ids in ids_lists[1:]:
            assert ids == first_ids
        
        # Should be sorted
        assert first_ids == sorted(first_ids)
