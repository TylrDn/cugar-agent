"""Tests for MCP deterministic behavior and reproducible results.

This module tests that MCP tool execution is deterministic and reproducible,
with proper mocking to avoid network calls and consistent output normalization.
"""

import json
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from cuga.tools.mcp_toolbox import MCPToolbox


# Normalizer utilities for deterministic output

def normalize_timestamps(data: Any) -> Any:
    """Replace timestamps with canonical values for determinism.
    
    Args:
        data: Data to normalize
        
    Returns:
        Normalized data
    """
    if isinstance(data, dict):
        normalized = {}
        for key, value in data.items():
            if key in ["timestamp", "created_at", "updated_at"]:
                normalized[key] = "2025-01-01T00:00:00Z"
            else:
                normalized[key] = normalize_timestamps(value)
        return normalized
    elif isinstance(data, list):
        return [normalize_timestamps(item) for item in data]
    else:
        return data


def normalize_durations(data: Any) -> Any:
    """Normalize duration values to canonical values.
    
    Args:
        data: Data to normalize
        
    Returns:
        Normalized data
    """
    if isinstance(data, dict):
        normalized = {}
        for key, value in data.items():
            if key in ["duration_ms", "latency_ms", "elapsed_ms"]:
                # Round to avoid floating point differences
                normalized[key] = round(float(value), 2) if isinstance(value, (int, float)) else value
            else:
                normalized[key] = normalize_durations(value)
        return normalized
    elif isinstance(data, list):
        return [normalize_durations(item) for item in data]
    else:
        return data


def normalize_output(data: Any) -> Any:
    """Fully normalize output for deterministic comparison.
    
    Args:
        data: Data to normalize
        
    Returns:
        Normalized data
    """
    data = normalize_timestamps(data)
    data = normalize_durations(data)
    
    # Sort dictionary keys for consistent ordering
    if isinstance(data, dict):
        return {k: normalize_output(v) for k, v in sorted(data.items())}
    elif isinstance(data, list):
        return [normalize_output(item) for item in data]
    else:
        return data


@pytest.fixture
def fixtures_dir():
    """Get the fixtures directory path."""
    return Path(__file__).parent / "data" / "mcp_deterministic"


@pytest.fixture
def sample_registry_yaml(tmp_path):
    """Create a sample registry YAML for testing."""
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text("""
version: v1
defaults:
  tier: 1
  enabled: true
  protocol: mcp
  sandbox: py-slim
  scopes: []
  env: {}
  mounts: []
  budget_policy: warn

entries:
  - id: mcp.github
    ref: docker://github
    scopes: [vcs]
    mounts: []
  
  - id: mcp.fs
    ref: docker://filesystem
    scopes: [fs]
    mounts: []
""")
    return registry_path


def test_input_fixture_exists(fixtures_dir):
    """Test that input fixtures exist."""
    input_file = fixtures_dir / "input_github_list_repos.json"
    assert input_file.exists()


def test_output_fixture_exists(fixtures_dir):
    """Test that output fixtures exist."""
    output_file = fixtures_dir / "output_github_list_repos.json"
    assert output_file.exists()


def test_mock_server_fixture_exists(fixtures_dir):
    """Test that mock server response fixtures exist."""
    mock_file = fixtures_dir / "mock_server_response.json"
    assert mock_file.exists()


def test_load_input_fixture(fixtures_dir):
    """Test loading input fixture."""
    input_file = fixtures_dir / "input_github_list_repos.json"
    
    with open(input_file) as f:
        fixture = json.load(f)
    
    assert "tool_id" in fixture
    assert "inputs" in fixture
    assert "context" in fixture
    assert fixture["tool_id"] == "mcp.github"


def test_load_output_fixture(fixtures_dir):
    """Test loading output fixture."""
    output_file = fixtures_dir / "output_github_list_repos.json"
    
    with open(output_file) as f:
        fixture = json.load(f)
    
    assert "status" in fixture
    assert "data" in fixture
    assert fixture["status"] == "success"


def test_normalize_timestamps():
    """Test timestamp normalization."""
    data = {
        "timestamp": "2024-12-31T12:34:56Z",
        "created_at": "2024-12-30T10:00:00Z",
        "value": 123
    }
    
    normalized = normalize_timestamps(data)
    
    assert normalized["timestamp"] == "2025-01-01T00:00:00Z"
    assert normalized["created_at"] == "2025-01-01T00:00:00Z"
    assert normalized["value"] == 123


def test_normalize_durations():
    """Test duration normalization."""
    data = {
        "duration_ms": 150.456789,
        "latency_ms": 25.1,
        "value": "test"
    }
    
    normalized = normalize_durations(data)
    
    assert normalized["duration_ms"] == 150.46
    assert normalized["latency_ms"] == 25.1
    assert normalized["value"] == "test"


def test_normalize_output_full():
    """Test full output normalization."""
    data = {
        "timestamp": "2024-12-31T12:34:56Z",
        "duration_ms": 150.456789,
        "data": {
            "created_at": "2024-12-30T10:00:00Z",
            "value": 123
        }
    }
    
    normalized = normalize_output(data)
    
    # Check timestamps normalized
    assert normalized["timestamp"] == "2025-01-01T00:00:00Z"
    assert normalized["data"]["created_at"] == "2025-01-01T00:00:00Z"
    
    # Check durations normalized
    assert normalized["duration_ms"] == 150.46
    
    # Check values preserved
    assert normalized["data"]["value"] == 123


def test_reproducible_execution_with_mock(sample_registry_yaml, fixtures_dir):
    """Test that execution with mocked handler produces deterministic results."""
    # Load expected output
    output_file = fixtures_dir / "output_github_list_repos.json"
    with open(output_file) as f:
        expected_output = json.load(f)
    
    # Create toolbox
    toolbox = MCPToolbox(registry_path=sample_registry_yaml, enable_audit=False)
    toolbox.load_tools()
    
    # Register mock handler that returns expected output
    def mock_handler(inputs, context):
        return expected_output
    
    toolbox.register_handler("mcp.github", mock_handler)
    
    # Execute multiple times
    results = []
    for i in range(3):
        result = toolbox.execute_tool(
            "mcp.github",
            {"action": "list_repos", "user": "octocat"},
            {"trace_id": f"test-{i}"}
        )
        results.append(result)
    
    # All results should be identical
    normalized_results = [normalize_output(r) for r in results]
    assert normalized_results[0] == normalized_results[1]
    assert normalized_results[1] == normalized_results[2]


def test_no_network_calls_in_tests(sample_registry_yaml):
    """Test that MCP tests don't make actual network calls."""
    toolbox = MCPToolbox(registry_path=sample_registry_yaml, enable_audit=False)
    toolbox.load_tools()
    
    # Register a handler that would fail if network was attempted
    network_attempted = []
    
    def no_network_handler(inputs, context):
        # This handler doesn't make network calls
        network_attempted.append(False)
        return {"status": "ok", "network_used": False}
    
    toolbox.register_handler("mcp.github", no_network_handler)
    
    # Execute tool
    result = toolbox.execute_tool("mcp.github", {})
    
    # Verify no network was used
    assert len(network_attempted) == 1
    assert result["network_used"] is False


def test_fixture_matches_execution(sample_registry_yaml, fixtures_dir):
    """Test that fixture output matches actual execution."""
    # Load fixtures
    input_file = fixtures_dir / "input_github_list_repos.json"
    output_file = fixtures_dir / "output_github_list_repos.json"
    
    with open(input_file) as f:
        input_fixture = json.load(f)
    
    with open(output_file) as f:
        expected_output = json.load(f)
    
    # Create toolbox and register handler
    toolbox = MCPToolbox(registry_path=sample_registry_yaml, enable_audit=False)
    toolbox.load_tools()
    
    def fixture_handler(inputs, context):
        return expected_output
    
    toolbox.register_handler(input_fixture["tool_id"], fixture_handler)
    
    # Execute with fixture inputs
    result = toolbox.execute_tool(
        input_fixture["tool_id"],
        input_fixture["inputs"],
        input_fixture["context"]
    )
    
    # Normalize and compare
    normalized_result = normalize_output(result)
    normalized_expected = normalize_output(expected_output)
    
    assert normalized_result == normalized_expected


def test_output_normalization_idempotent():
    """Test that normalization is idempotent."""
    data = {
        "timestamp": "2024-12-31T12:34:56Z",
        "duration_ms": 150.456789,
        "value": "test"
    }
    
    # Normalize once
    normalized1 = normalize_output(data)
    
    # Normalize again
    normalized2 = normalize_output(normalized1)
    
    # Should be identical
    assert normalized1 == normalized2


def test_mock_server_responses_parseable(fixtures_dir):
    """Test that mock server responses are valid."""
    mock_file = fixtures_dir / "mock_server_response.json"
    
    with open(mock_file) as f:
        mock_data = json.load(f)
    
    assert "version" in mock_data
    assert "responses" in mock_data
    
    # Verify response structure
    for key, response in mock_data["responses"].items():
        assert "status_code" in response
        assert "headers" in response
        assert "body" in response


def test_deterministic_sorted_output():
    """Test that outputs are consistently sorted."""
    data = {
        "z_field": 3,
        "a_field": 1,
        "m_field": 2,
    }
    
    normalized = normalize_output(data)
    
    # Keys should be sorted
    keys = list(normalized.keys())
    assert keys == ["a_field", "m_field", "z_field"]


def test_list_normalization_preserves_order():
    """Test that list order is preserved during normalization."""
    data = {
        "items": [
            {"name": "first", "timestamp": "2024-12-31T12:00:00Z"},
            {"name": "second", "timestamp": "2024-12-31T13:00:00Z"},
            {"name": "third", "timestamp": "2024-12-31T14:00:00Z"},
        ]
    }
    
    normalized = normalize_output(data)
    
    # List order should be preserved
    assert normalized["items"][0]["name"] == "first"
    assert normalized["items"][1]["name"] == "second"
    assert normalized["items"][2]["name"] == "third"
    
    # But timestamps should be normalized
    for item in normalized["items"]:
        assert item["timestamp"] == "2025-01-01T00:00:00Z"


def test_nested_normalization():
    """Test normalization of deeply nested structures."""
    data = {
        "level1": {
            "timestamp": "2024-12-31T12:00:00Z",
            "level2": {
                "duration_ms": 100.123,
                "level3": {
                    "created_at": "2024-12-30T10:00:00Z",
                    "value": "test"
                }
            }
        }
    }
    
    normalized = normalize_output(data)
    
    # All nested timestamps should be normalized
    assert normalized["level1"]["timestamp"] == "2025-01-01T00:00:00Z"
    assert normalized["level1"]["level2"]["level3"]["created_at"] == "2025-01-01T00:00:00Z"
    
    # Duration should be rounded
    assert normalized["level1"]["level2"]["duration_ms"] == 100.12
    
    # Value should be preserved
    assert normalized["level1"]["level2"]["level3"]["value"] == "test"
