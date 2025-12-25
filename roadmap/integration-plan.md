## Milestone 1: Tier 1 registry + compose wiring
Acceptance: registry.yaml lists all Tier 1 tools enabled; compose starts orchestrator + mcp.e2b/mcp.fs/mcp.web/mcp.vcs with healthchecks. Kill-switch: revert to minimal orchestrator-only profile.

## Milestone 2: Sandbox enforcement
Acceptance: sandbox profiles py-slim/full and node-slim/full applied per tool; read-only mounts verified for fs tools. Kill-switch: disable sandbox profiles in compose and fall back to in-process mock tools.

## Milestone 3: Observability/budget hooks
Acceptance: AGENT_* envs control sampling, latency, and budgets; LangFuse/LangSmith/OTEL endpoints configurable; traces emitted per tool. Kill-switch: set AGENT_TRACE_SAMPLE_RATE=0 and AGENT_BUDGET_ENFORCE=warn to disable hard enforcement.

## Milestone 4: Tier 2 opt-in modules
Acceptance: Tier 2 entries present but disabled; compose profiles `tier2` start optional services (observability, vector-db). Kill-switch: remove profile from compose invocation.

## Milestone 5: Registry-driven hot-swap
Acceptance: tool replacements via registry change only (no code edits) with successful smoke tests; deterministic merge behavior upheld. Kill-switch: lock registry to last known good version and disable reload.
