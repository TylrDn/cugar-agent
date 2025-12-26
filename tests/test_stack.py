import asyncio
import pytest
from fastapi.testclient import TestClient

from cuga.sandbox.isolation import budget_within_limits, filter_env, validate_tool_path
from cuga.registry.loader import Registry
from cuga.planner.core import Planner
from cuga.coordinator.core import Coordinator
from cuga.workers.base import Worker
from cuga.memory.vector import VectorMemory
from cuga.observability import InMemoryTracer
from cuga.backend.app import app, registry_path


def test_guardrails_and_budget():
    env = {"AGENT_BUDGET_CEILING": "10", "SECRET": "nope"}
    filtered = filter_env(env)
    assert "SECRET" not in filtered
    validate_tool_path("cuga.modular.tools.echo")
    with pytest.raises(ValueError):
        validate_tool_path("os")
    assert budget_within_limits(5, 10)
    assert not budget_within_limits(11, 10)


def test_registry_reload_and_ordering(tmp_path):
    reg = Registry(registry_path)
    assert any(not e.enabled for e in reg.entries if e.tier == 2)
    content = """
version: v1
defaults: {tier: 1, enabled: true, sandbox: py-slim}
entries:
  - id: b
    ref: docker://b
    scopes: [exec]
  - id: a
    ref: docker://a
    scopes: [exec]
"""
    reg.hot_reload(content)
    ids = [e.id for e in reg.entries]
    assert ids == sorted(ids)


def test_planner_coordinator_round_robin():
    tracer = InMemoryTracer()
    planner = Planner(tracer=tracer)
    steps = asyncio.run(planner.plan("hello", metadata={"trace_id": "t1"}))
    plan = steps + steps
    coord = Coordinator([Worker("w1"), Worker("w2")], tracer=tracer)
    results = []
    async def _collect():
        async for item in coord.run(plan, trace_id="t1"):
            results.append(item["worker"])
    asyncio.run(_collect())
    assert results == ["w1", "w2"]
    assert any(span.attributes.get("tool") for span in tracer.spans)


def test_tool_schema_validation():
    worker = Worker("w")
    class Step:
        tool = "cuga.modular.tools.echo"
        params = {}
    with pytest.raises(ValueError):
        asyncio.run(worker.execute(Step(), trace_id="t1"))


def test_observability_redaction():
    tracer = InMemoryTracer()
    span = tracer.start_span("test", secret_value="123", token="abc")
    span.end()
    assert tracer.spans[0].attributes["secret_value"] == "[redacted]"
    assert tracer.spans[0].attributes["token"] == "[redacted]"


def test_vector_memory_retention_and_batching():
    mem = VectorMemory(ttl_seconds=0.1, max_items=2)
    asyncio.run(mem.batch_upsert([{"id": 1}, {"id": 2}]))
    asyncio.run(mem.batch_upsert([{"id": 3}]))
    res = asyncio.run(mem.similarity_search("q", k=5))
    assert len(res) == 2 and res[0]["id"] == 2 and res[1]["id"] == 3
    asyncio.run(asyncio.sleep(0.2))
    assert not asyncio.run(mem.similarity_search("q"))


def test_fastapi_surface(monkeypatch):
    client = TestClient(app)
    monkeypatch.setenv("AGENT_TOKEN", "t")
    r = client.get("/health", headers={"X-Token": "t"})
    assert r.status_code == 200
    bad = client.get("/health", headers={"X-Token": "bad"})
    assert bad.status_code == 401
    plan = client.post("/plan", headers={"X-Token": "t"}, json={"goal": "hi"})
    assert plan.json()["steps"]
    stream = client.post("/execute", headers={"X-Token": "t"}, json={"goal": "hi"})
    assert stream.status_code == 200
    assert any(line.startswith("data") for line in stream.iter_text().splitlines())
