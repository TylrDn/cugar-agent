# Architecture Overview

Assumptions: Python 3.12+ runtime, MCP registry + lifecycle already present, and Langflow + ALTK operate as the orchestration control plane for the agent. The term **orchestrator** refers to the single logical service representing **Langflow + ALTK** (even if internally split).

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

## Control vs Data Flow
- **Control flow:** orchestration → core interfaces → adapters → sandbox launch; governed by the registry and profile selection.
- **Data flow:** sandboxed adapters read/write only within their scoped mounts, emit traces to observability sinks, and return sanitized results to the orchestrator.

## Authoritative Core Interfaces
- `ToolBus`: broker between orchestrator intents and adapter calls.
- `StateStore`: persistence boundary for plans, runs, and artifacts.
- `VectorIndex`: retrieval interface for embeddings or semantic search.
- `TraceSink`: export pipeline for traces and audit events (e.g., OTEL/LangFuse/LangSmith).
- `SecretStore`: provider for scoped credentials (env, secret stores, or injected at runtime).
- `ProfileRegistry`: single source of truth for which tools/profiles are active per tier.

Guardrails: updates to any profile or registry must first strengthen the guardrail section in `AGENTS.md` (tool allow/deny lists, escalation ceilings, redaction rules, budget caps) before enabling new Tier 1 defaults.
