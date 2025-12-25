# Usage Guide

This guide shows how to run, compose, and extend the CUGAR Agent stack via CLI and Python. All commands assume Python >=3.10 and `uv` for environment management.

## Setup
```bash
uv sync --all-extras --dev
uv run playwright install --with-deps chromium
cp .env.example .env
```
Set provider keys (e.g., `OPENAI_API_KEY`, `LANGFUSE_SECRET`) inside `.env` or your shell.

## CLI Flows
The Typer CLI is exposed as `uv run cuga`.

### Start a demo agent
```bash
uv run cuga start demo
```
- Starts registry + demo tool servers on the default sandbox profile.
- Uses `configs/agent.demo.yaml` for model + policy defaults.

### Run a goal with LangGraph planner
```bash
uv run python examples/run_langgraph_demo.py --goal "Draft a changelog from pull request notes" \
  --profile demo_power --observability langfuse
```
- Plans with ReAct; executes via LangChain tool runtime.
- Sends traces to Langfuse if `LANGFUSE_SECRET` is set.

### Inspect registries and profiles
```bash
uv run cuga registry list --profile demo_power
uv run cuga profile validate --profile demo_power
```
- Registries live in `config/` and `registry.yaml`.
- Profiles apply sandbox isolation and guardrail enforcement.

### Run memory/RAG helpers
```bash
uv run python scripts/load_corpus.py --source rag/sources --backend chroma
uv run python examples/rag_query.py --query "How does the planner select tools?" --backend chroma
```
- Uses `memory/vector_store.py` with in-memory fallback when no backend is reachable.

### Multi-agent hand-off
```bash
uv run python examples/multi_agent_dispatch.py --goal "Summarize docs and propose next steps"
```
- Demonstrates coordinator/worker/tool-user roles with shared memory summaries.

## Python API Quickstart
```python
from cuga.modular.agents import PlannerAgent, WorkerAgent
from cuga.modular.tools import ToolRegistry, ToolSpec
from cuga.modular.memory import VectorMemory

registry = ToolRegistry([
    ToolSpec(name="echo", description="echo text", handler=lambda i, c: i["text"]),
])
memory = VectorMemory()
planner = PlannerAgent(registry=registry, memory=memory)
worker = WorkerAgent(registry=registry, memory=memory)

plan = planner.plan(goal="echo hello", metadata={"profile": "demo"})
result = worker.execute(plan.steps)
print(result.output)
```

## Adding a Tool
1. Implement `ToolSpec` in `tools/registry.py` or wrap an MCP server.
2. Register it via `ToolRegistry([...])` or YAML in `configs/tools.yaml`.
3. Add tests under `tests/` to cover handler success/failure.

## LlamaIndex RAG Path
- Configure `configs/rag.yaml` with storage path or remote vector DB.
- Use `rag/loader.py` to ingest content and `rag/retriever.py` for queries.
- Toggle `RAG_ENABLED=true` in `.env` to opt-in.

## Observability Hooks
- **Langfuse**: set `LANGFUSE_SECRET` + `LANGFUSE_PUBLIC_KEY`; calls are emitted via `observability/langfuse.py`.
- **OpenInference/Traceloop**: enable with `OPENINFERENCE_ENABLED=true` and configure URLs in `configs/observability.yaml`.
- All emitters redact secrets and run in the current profile sandbox.

## Troubleshooting
- Ports 7860/8000/8001/9000 must be free for demos.
- If Playwright browsers are missing, re-run `uv run playwright install --with-deps chromium`.
- Use `--verbose` flags for detailed logs; traces are stored under `logs/` when enabled.
