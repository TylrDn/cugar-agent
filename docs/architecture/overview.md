# Architecture Overview

Assumptions: Python 3.12+, MCP registry + lifecycle already exist, and Langflow + ALTK serve as the orchestration control plane for the CUGAR agent. Guardrails live in `AGENTS.md` and must be tightened before enabling new Tier 1 inventory.

```
Langflow UI / ALTK
        ↓
Agent Orchestrator (CUGAR)
        ↓
   Core Interfaces
        ↓
 Tool Adapters (MCP)
        ↓
Sandboxed MCP Runners
        ↓
   State + Tracing
```

Data flow (left lane): request → orchestrator → ToolBus → MCP adapter → sandboxed runner → responses/artifacts → StateStore/VectorIndex.
Control flow (right lane): guardrails + registry lookup → profile selection → sandbox policy (mounts/network/limits) → budget + tracing hooks → result shaping.

Authoritative core interfaces (replaceable behind DI): ToolBus, StateStore, VectorIndex, TraceSink, SecretStore, ProfileRegistry.

The “orchestrator” refers to the single logical service representing Langflow + ALTK (even if internally split or scaled).

Observability (OTEL/LangFuse/LangSmith) and budgets are configured via environment, not code, and align with the sandboxes in `docs/compute/sandboxes.md` and registry entries in `docs/mcp/registry.yaml`.
