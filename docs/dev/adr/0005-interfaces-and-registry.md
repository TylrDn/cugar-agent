# ADR 0005: Interfaces-first registry-driven integrations

## Status
Accepted

## Context
CUGAR coordinates MCP tools through Langflow + ALTK as the orchestration control plane. Root guardrails require profile isolation, deterministic registry merges, sandboxed execution, and env-driven budgets/observability.

## Decision
- Core contracts are limited to ToolBus, StateStore, VectorIndex, TraceSink, SecretStore, and ProfileRegistry; vendor SDKs stay out of core.
- `docs/mcp/registry.yaml` is the single source of truth for tool availability, tiers, sandboxes, env hooks, and mounts; tables are generated (build/gen_tiers_table.py) to avoid doc drift.
- Tier 1 integrations default to enabled; Tier 2 entries remain opt-in behind compose profiles and registry `enabled: false` flags.
- Observability and budget controls are driven by environment (`docs/observability/config.md`) and applied at orchestration/runtime boundaries.

## Consequences
- Adding or swapping a tool only requires registry edits and an adapter bound to the interfaces; core code remains unchanged.
- Compose wiring and sandbox profiles mirror registry hints, enabling hot-swap and least-privilege mounts.
- Failing guardrails (profiles, budgets, trace redaction) block Tier 1 rollout until addressed in `AGENTS.md`, the registry, and generated docs.
