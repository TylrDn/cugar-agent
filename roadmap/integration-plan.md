# Integration Plan

Pre-Task (blocking): Update GUARDRAILS in `AGENTS.md` (tool allowlist/denylist, escalation ceilings, redaction rules, budget caps) before enabling Tier 1 defaults.

## Milestone 1: Tier 1 registry + compose wiring
Acceptance: `docs/mcp/registry.yaml` lists all Tier 1 tools enabled with mounts/env matching compose; orchestrator depends on Tier 1 services with healthchecks. Kill-switch: revert to orchestrator-only compose and disable Tier 1 entries.

## Milestone 2: Sandbox enforcement
Acceptance: py/node slim/full profiles applied per registry sandbox; read-only mounts enforced where possible; E2B/Docker exec pinned to /workdir. Kill-switch: disable sandbox services and switch to mock adapters.

## Milestone 3: Observability & budgets
Acceptance: AGENT_* and OTEL/LangFuse/LangSmith env keys respected; budgets enforced per run/day with `warn|block`; traces sampled per config. Kill-switch: set AGENT_TRACE_SAMPLE_RATE=0 and AGENT_BUDGET_ENFORCE=warn.

## Milestone 4: Tier 2 opt-in modules
Acceptance: Tier 2 entries present but `enabled: false`; compose `tier2` profile starts optional observability/vector-db; network limits documented. Kill-switch: omit `--profile tier2` and leave registry flags false.

## Milestone 5: Registry-driven hot-swap
Acceptance: tool replacements occur via registry edits only; doc tables auto-regenerated; deterministic sort verified by tests. Kill-switch: freeze registry at last known good revision and block reloads.
