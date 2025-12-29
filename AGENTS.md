# AGENTS.md (Single Source of Truth)

> This directory inherits from root `AGENTS.md` (canonical). Conflicts resolve to root.

## 1. Scope & Precedence
- Root guardrails are canonical for all subdirectories; add directory-specific `AGENTS.md` only to tighten rules, never to relax them.
- Allowlisted tools live under `cuga.modular.tools.*`; any denylisted or unknown module import MUST be rejected before execution.
- Tier 1 defaults are enabled only when allowlists/denylists, escalation ceilings, secret redaction, and budget caps are present and in sync with the registry.
- Registry edits are the sole mechanism for tool swaps; hot swaps MUST go through registry.yaml diffs with deterministic ordering.
- PlannerAgent accepts `(goal: str, metadata: dict)` and returns an ordered plan with streaming-friendly traces; WorkerAgent executes ordered steps; CoordinatorAgent preserves trace ordering with thread-safe round-robin worker selection.

## 2. Profile Isolation
- MUST run deterministically offline; avoid network after setup; mock/record external calls.
- MUST prioritize security-first designs: least privilege, sanitized inputs, no `eval`/`exec`.
- MUST keep memory/profile data isolated per profile; no cross-profile leakage; default profile falls back to `memory.profile` when unspecified.

## 3. Registry Hygiene
- Registry entries MUST declare sandbox profile (`py/node slim|full`, `orchestrator`), read-only mounts, and `/workdir` pinning for exec sandboxes.
- Compose mounts/env for Tier 1 entries MUST match `docs/mcp/registry.yaml` and include health checks; Tier 2 entries default to `enabled: false`.
- Env keys MUST wire observability (`OTEL_*`, LangFuse/LangSmith) and budget enforcement (`AGENT_*`) with `warn|block` policies spelled out.
  Current policy: allowlist `cuga.modular.tools.*` only; denylist any external module imports; env allowlist `AGENT_*`, `OTEL_*`,
  `LANGFUSE_*`, `OPENINFERENCE_*`, `TRACELOOP_*`. Budget ceilings default `AGENT_BUDGET_CEILING=100`, escalation max `AGENT_ESCALATION_MAX=2`,
  and redaction removes values matching `secret`, `token`, or `password` keys before logging.

## 4. Sandbox Expectations
- Tool handler signature: `(inputs: Dict[str, Any], context: Dict[str, Any]) -> Any`; context includes `profile`, `trace_id`.
- Dynamic imports MUST be restricted to `cuga.modular.tools.*`; reject relative/absolute paths outside this namespace and denylisted modules.
- Tools MUST declare parameters/IO expectations; MUST NOT perform network I/O unless explicitly allowed by profile; honor budget ceilings and redaction rules for outputs/logs.
- Forbidden: `eval`/`exec`, writing outside sandbox, spawning daemons, or swallowing errors silently; read-only mounts are the default.

## 5. Audit / Trace Semantics
- Logs MUST be structured (JSON-friendly) and omit PII; redact secrets before emission; include reason when budgets trigger warn/block decisions.
- `trace_id` MUST propagate across planner/worker/coordinator, CLI, and tools with ordered plan traces preserved under concurrency.
- Emit events for plan creation, tool selection, execution start/stop, backend connections, errors, and budget/registry decisions.

## 6. Documentation Update Rules
- Config changes MUST update tests and docs in the same PR; env parsing MUST clamp `PLANNER_MAX_STEPS` to 1..50 and `MODEL_TEMPERATURE` to 0..2 with warnings on invalid values.
- Edit `AGENTS.md` first when modifying guardrails; update `CHANGELOG.md` (`## vNext`) with summary and keep migration notes current for breaking changes.
- Document registry and sandbox guardrail adjustments in `CHANGELOG.md` alongside updated tests.
- Keep contributor-facing docs synchronized with guardrail expectations: refresh README/PRODUCTION readiness notes and the repo to-do tracker (`todo1.md`) when altering registry allowlists, budgets, or redaction policies. Run `python scripts/verify_guardrails.py` after every guardrail or registry edit and capture any new follow-ups in the to-do list.

## 7. Verification & No Conflicting Guardrails
- Tests MUST assert planner does not return all tools blindly; vector scores correlate with similarity and are ordered.
- Round-robin coordinator scheduling MUST be verified under concurrent calls; planner/worker/coordinator interface guardrails MUST be covered by automated checks.
- Import guardrails MUST be enforced (reject non-`cuga.modular.tools.*`); env parsing tests MUST cover invalid/edge values and fallback behavior.
- Any change violating or adjusting guardrails MUST update this file plus corresponding tests in the same PR; non-root `AGENTS.md` MUST only declare inheritance, never canonical status.

## 8. Contributor Checklist (TL;DR)
- Read this file first and confirm registry/sandbox edits follow the allowlist/denylist rules.
- Keep docs (README, PRODUCTION readiness, security/policies) and `todo1.md` aligned with any guardrail or registry change.
- Run `python scripts/verify_guardrails.py` and the stability harness before merging; add new tests when planner/worker/coordinator interfaces evolve.
