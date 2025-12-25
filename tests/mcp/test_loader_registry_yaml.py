from __future__ import annotations

from pathlib import Path

import pytest

from mcp.loader import OpenAPISchemaCache, load_registry


@pytest.fixture
def sample_schema() -> dict:
    return {
        "paths": {
            "/echo": {"post": {"operationId": "echoMessage"}},
            "/contacts": {"post": {"operationId": "fetchContacts"}},
        }
    }


def test_load_registry_respects_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, sample_schema: dict) -> None:
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(
        """
servers:
  disabled_server:
    url: http://mock
    enabled_env: DISABLE_ME
    tools:
      - capability: Test
        action: Echo
        operation_id: echoMessage
  enabled_server:
    url: http://mock
    schema: http://mock/openapi.json
    tools:
      - capability: CRM
        action: Fetch contacts
        operation_id: fetchContacts
        cost: 2
        latency: 3
        description: fetch contacts safely
        """
    )
    monkeypatch.setenv("DISABLE_ME", "0")
    registry = load_registry(registry_path, fetcher=lambda _: sample_schema, cache=OpenAPISchemaCache())

    assert len(registry.servers) == 1
    server = registry.servers[0]
    assert server.name == "enabled_server"
    assert server.tools[0].path == "/contacts"
    assert registry.tools()[0].display_name == "CRM · Fetch contacts"
    assert registry.tools()[0].cost == 2.0
    assert registry.tools()[0].latency == 3.0
    assert "contacts" in registry.tools()[0].description
