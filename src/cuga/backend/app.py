from __future__ import annotations

import os
import secrets
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from cuga.planner.core import Planner
from cuga.coordinator.core import Coordinator
from cuga.workers.base import Worker
from cuga.registry.loader import Registry
from cuga.observability import propagate_trace
from pathlib import Path

registry_path = Path("docs/mcp/registry.yaml")
planner = Planner()
coordinator = Coordinator([Worker("w1"), Worker("w2")])
registry = Registry(registry_path)

app = FastAPI(title="Cuga Backend")


@app.middleware("http")
async def budget_guard(request, call_next):
    expected_token = os.environ.get("AGENT_TOKEN")
    if not expected_token:
        raise HTTPException(status_code=500, detail="agent token not configured")

    token = request.headers.get("X-Token")
    if not secrets.compare_digest(token or "", expected_token):
        raise HTTPException(status_code=401, detail="unauthorized")
    ceiling = int(os.environ.get("AGENT_BUDGET_CEILING", "100"))
    spent = int(request.headers.get("X-Budget-Spent", "0"))
    if spent > ceiling:
        return JSONResponse(status_code=429, content={"detail": "budget exceeded"})
    response = await call_next(request)
    if not hasattr(response, "headers"):
        response = JSONResponse(status_code=getattr(response, "status_code", 200), content=getattr(response, "content", response))
    response.headers["X-Budget-Ceiling"] = str(ceiling)
    return response


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/plan")
async def plan(payload: dict, x_trace_id: str | None = Header(default=None)):
    propagate_trace(x_trace_id or "api")
    steps = await planner.plan(payload.get("goal", ""), metadata={"trace_id": x_trace_id or "api"})
    return {"steps": [s.tool for s in steps]}


@app.post("/execute")
async def execute(payload: dict, x_trace_id: str | None = Header(default=None)):
    trace = x_trace_id or "api"
    steps = await planner.plan(payload.get("goal", ""), metadata={"trace_id": trace})
    async def iterator():
        async for item in coordinator.run(steps, trace_id=trace):
            yield (f"data: {item}\n\n").encode()
    return StreamingResponse(iterator(), media_type="text/event-stream")
