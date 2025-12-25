from __future__ import annotations

import httpx
import pytest

from mcp.runner import MCPRunner
from mcp.types import MCPTool
from tests.mcp.mock_server import app


@pytest.fixture(scope="module")
def http_client() -> httpx.Client:
    transport = httpx.ASGITransport(app=app)
    client = httpx.Client(transport=transport, base_url="http://mockserver")
    yield client
    client.close()


def test_runner_invokes_successfully(http_client: httpx.Client) -> None:
    runner = MCPRunner(client=http_client)
    tool = MCPTool(
        capability="Echo",
        action="Send",
        operation_id="echoMessage",
        method="POST",
        path="/echo",
        server="mock",
        base_url="http://mockserver",
    )
    result = runner.invoke(tool, {"message": "hello"})
    assert result.ok is True
    assert result.output == {"echo": {"message": "hello"}}


def test_runner_reports_failure(http_client: httpx.Client) -> None:
    runner = MCPRunner(client=http_client, retries=0)
    tool = MCPTool(
        capability="CRM",
        action="Fetch contacts",
        operation_id="fetchContacts",
        method="POST",
        path="/contacts",
        server="mock",
        base_url="http://mockserver",
    )
    result = runner.invoke(tool, {"fail": True})
    assert result.ok is False
    assert result.status_code == 400
