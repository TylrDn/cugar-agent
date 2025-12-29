# CUGAR Agent (2025 Edition)

[![CI](https://github.com/TylrDn/cugar-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/TylrDn/cugar-agent/actions/workflows/ci.yml)
[![Tests](https://github.com/TylrDn/cugar-agent/actions/workflows/tests.yml/badge.svg)](https://github.com/TylrDn/cugar-agent/actions/workflows/tests.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Coverage](https://img.shields.io/badge/coverage-pytest--cov-success)](./TESTING.md)

CUGAR Agent is a production-grade, modular agent stack that embraces 2025’s best practices for LangGraph/LangChain orchestration, LlamaIndex-powered RAG, CrewAI/AutoGen-style multi-agent patterns, and modern observability (Langfuse/OpenInference/Traceloop). The repository is optimized for rapid setup, reproducible demos, and safe extension into enterprise environments.
Policy and change-management guardrails are maintained in [AGENTS.md](AGENTS.md) and must be reviewed before modifying agents or tools.

## At a Glance
- **Composable agent graph**: Planner → Tool/User executor → Memory+Observability hooks, wired for LangGraph.
- **RAG-ready**: LlamaIndex loader/retriever scaffolding with pluggable vector stores (Chroma, Qdrant, Weaviate, Milvus).
- **Multi-agent**: CrewAI/AutoGen-compatible patterns and coordination helpers.
- **Observability-first**: Langfuse/OpenInference emitters, structured audit logs, profile-aware sandboxing.
- **Developer experience**: Typer CLI, Makefile tasks, uv-based env management, Ruff/Black/isort + mypy, pytest+coverage, pre-commit.
- **Deployment**: Dockerfile, GitHub Actions CI/CD, sample configs and .env.example for cloud/on-prem setups.

## Architecture
```
                       ┌──────────────────────────┐
                       │        Controller        │
                       │ (policy + correlation ID)│
                       └────────────┬─────────────┘
                                    │
                           plan(goal, registry)
                                    │
┌──────────────┐          ┌─────────▼─────────┐          ┌────────────────────┐
│ Registry/CFG │──sandbox▶│    Planner        │──steps──▶│   Executor/Tools   │
│ (Hydra/Dyn)  │          │ (ReAct/Plan&Exec) │          │ (LCEL, MCP, HTTP)  │
└──────────────┘          └─────────┬─────────┘          └─────────┬──────────┘
                                    │                              │
                          traces + memory writes         Langfuse/OpenInference
                                    │                              │
                            ┌───────▼────────┐                   ┌─▼────────┐
                            │ Memory / RAG   │◀────context───────│  Clients │
                            │ (LlamaIndex)   │                   │ (CLI/API)│
                            └────────────────┘                   └──────────┘
```

For a role-by-role, mode-aware walkthrough of how the controller, planners, executors, and MCP tool packs fit together (plus configuration keys), see [docs/agents/architecture.md](docs/agents/architecture.md).

## Quickstart
```bash
# 1) Install (Python >=3.10)
uv sync --all-extras --dev
uv run playwright install --with-deps chromium

# 2) Configure environment
cp .env.example .env
# set OPENAI_API_KEY / LANGFUSE_SECRET / etc inside .env

# 3) Run demo agent locally
uv run cuga start demo

# 4) Try modular stack example
uv run python examples/run_langgraph_demo.py --goal "triage a support ticket"
```

## Installation
- **Dependencies**: `uv` (or `pip`), optional browsers for Playwright, optional vector DB service (Chroma/Weaviate/Qdrant/Milvus).
- **Development**: `uv sync --all-extras --dev` installs dev + optional extras (`memory`, `sandbox`, `groq`, etc.).
- **Pre-commit**: `uv run pre-commit install` then `uv run pre-commit run --all-files`.

## Configuration
- `.env.example` lists required variables for LLMs, tracing, and storage.
- `configs/` holds YAML/TOML profiles for agents, LangGraph graphs, memory backends, and observability.
- `registry.yaml` and `config/` house MCP/registry defaults; use `scripts/verify_guardrails.py` before shipping changes.

## Guardrails & Change Management
- Review [AGENTS.md](AGENTS.md) before altering planners, tools, or registry entries; it is the single source of truth for allowlists, sandbox expectations, budgets, and redaction.
- After touching guardrails or registry fragments, run `python scripts/verify_guardrails.py` and update `CHANGELOG.md` under `## vNext` plus `todo1.md` with any new follow-ups.
- Keep production checklists ([PRODUCTION_READINESS.md](PRODUCTION_READINESS.md)) and security docs in sync with guardrail adjustments so downstream users understand the default policies and where to override them.

## Agent Types
- **Planner**: ReAct or Plan-and-Execute; emits steps with policy-aware cost/latency hints.
- **Tool Executor**: LCEL/LangChain tools, MCP adapters, HTTP/OpenAPI runners with sandboxed registry resolution.
- **RAG/Data Agent**: LlamaIndex loader+retriever (docs in `rag/`), vector memory connectors in `memory/`.
- **Coordinator**: CrewAI/AutoGen-like orchestrator for multi-agent hand-offs.
- **Observer**: Langfuse/OpenInference emitters with correlation IDs and redaction hooks.

See `AGENTS.md` for role details and `USAGE.md` for end-to-end flows.

## RAG Setup
- Drop documents into `rag/sources/` or configure a remote store.
- Choose a backend in `configs/memory.yaml` (chroma|qdrant|weaviate|milvus|local).
- Run `uv run python scripts/load_corpus.py --source rag/sources --backend chroma`.
- Query via `uv run python examples/rag_query.py --query "How do I add a new MCP tool?"`.

## Memory & State
- `memory/` exposes `VectorMemory` (in-memory fallback), summarization hooks, and profile-scoped stores.
- State keys are namespaced by profile to preserve sandbox isolation.
- Persistence is opt-in; see `configs/memory.yaml` and `TESTING.md` for guidance.

## Observability
- Langfuse client is wired via `observability/langfuse.py` with sampling + PII redaction hooks.
- OpenInference/Traceloop emitters are optional and can be toggled per profile.
- Structured audit logs live under `logs/` when enabled; avoid committing artifacts.

## Multi-Agent & Coordination
- `agents/` outlines planner/worker/tool-user patterns and how to register them with CrewAI/AutoGen.
- `examples/multi_agent_dispatch.py` demonstrates round-robin delegation with shared vector context.
- Hand-offs carry correlation IDs and redacted summaries, not raw prompts.

## Testing & Quality Gates
- Run `make lint test typecheck` locally.
- Pytest with coverage is configured (see `TESTING.md`).
- CI (GitHub Actions) runs lint, type-check, tests, and guardrail verification on pushes/PRs.

## FAQ
- **Which LLMs are supported?** Any LangChain/LiteLLM-compatible model (OpenAI, Azure, Groq, IBM watsonx, Google GenAI).
- **Do I need a vector DB?** Not for quickstarts; an in-memory store is bundled. For production use Chroma/Qdrant/Weaviate/Milvus.
- **How do I add a new tool?** Implement `ToolSpec` in `tools/registry.py` or wrap an MCP server; see `USAGE.md`.
- **Is this production-ready?** Core stack follows sandboxed, profile-scoped design with observability. Harden configs before internet-facing use.

## Roadmap Highlights
- Streaming-first ReAct policies with beta support for Strands/semantic state machines.
- Built-in eval harness for self-play and regression suites.
- Optional LangServe or FastAPI hosting for SaaS-style deployments (see `ROADMAP.md`).

## License
Apache 2.0. See [LICENSE](LICENSE).
