from __future__ import annotations

import httpx

from cuga.agents.executor import ExecutionContext, Executor
from cuga.agents.planner import Planner
from cuga.agents.registry import ToolRegistry
from mcp.loader import OpenAPISchemaCache, load_registry, register_tools
from mcp.runner import MCPRunner
from tests.mcp.mock_server import app


def test_planner_executor_runs_mcp_tool(tmp_path) -> None:
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(
        """
servers:
  planner_demo:
    url: http://mockserver
    tools:
      - capability: CRM
        action: Fetch contacts
        operation_id: fetchContacts
        description: Fetch contacts from mock CRM
        cost: 1
        latency: 1
        """
    )

    schema_cache = OpenAPISchemaCache()
    schema_cache.get("http://mockserver/openapi.json", lambda _: app.openapi())
    mcp_registry = load_registry(registry_path, fetcher=lambda _: app.openapi(), cache=schema_cache)

    transport = httpx.ASGITransport(app=app)
    http_client = httpx.Client(transport=transport, base_url="http://mockserver")
    runner = MCPRunner(client=http_client)

    registry = ToolRegistry()
    register_tools(registry, mcp_registry, runner, profile="demo")

    planner = Planner()
    plan = planner.plan("Fetch contacts", registry)
    assert plan.steps[0].tool == "CRM · Fetch contacts"

    executor = Executor()
    result = executor.execute_plan(plan.steps, registry, ExecutionContext(profile="demo"))
    assert result.output.get("contacts") == ["a", "b"]
