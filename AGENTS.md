# AGENTS.md (Single Source of Truth)

> This directory inherits from root `AGENTS.md` (canonical). Conflicts resolve to root.

## Framework Governance
- This file **and** `scripts/guardrails_check.py` form the code-as-policy framework that encodes safety and planning guardrails.
- Purpose: keep agents deterministic/offline, security-first, and auditable via a single normative source plus automated verifier.
- Maintenance: proposals MUST land via PRs modifying this file **and** the checker/tests in the same change; changelog entry required.
- Evolution: changes SHOULD include rationale, backwards-compatibility notes, and migration guidance to keep the guardrails scalable over time.

## Design Tenets
- MUST run deterministically offline; avoid network after setup; mock/record external calls.
- MUST prioritize security-first designs: least privilege, sanitized inputs, no `eval`/`exec`.
- SHOULD expose small, typed interfaces with explicit error handling and logging.
- MUST keep memory/profile data isolated per profile; no cross-profile leakage.

## Agent Roles & Interfaces
- PlannerAgent: input `(goal: str, metadata: dict)` → `AgentPlan` with ordered steps; MUST propagate `trace_id`.
- WorkerAgent: input `(steps, metadata)` → executes tools; MUST default profile to `memory.profile` when missing.
- CoordinatorAgent: orchestrates Planner + Workers; MUST preserve `trace_id` and plan trace ordering.
- All agents MUST accept/emit structured traces (dicts) carrying `trace_id`, step index, and profile.

## Planning Protocol
- Use ReAct/Plan-and-Execute hybrid: observe → reason → act; stop when goal met, max steps reached, or tool failure.
- Planner MUST select goal-relevant tools (never blindly all tools); rank by description/name similarity.
- Max steps derived from config/env, clamped to 1..50; temperature bounded 0..2 for stochastic steps.
- MUST record plan start/finish, selected tools, and stop condition in trace.

## Tool Contract
- Tool handler signature: `(inputs: Dict[str, Any], context: Dict[str, Any]) -> Any`; context includes `profile`, `trace_id`.
- Dynamic imports MUST be restricted to `cuga.modular.tools.*`; reject relative/absolute paths outside this namespace.
- Tools MUST declare parameters/IO expectations; MUST NOT perform network I/O unless explicitly allowed by profile.
- Forbidden: `eval`/`exec`, writing outside sandbox, spawning daemons, or swallowing errors silently.

## Memory & RAG
- Vector backends implement `VectorBackend` protocol (`connect`, `upsert`, `search` returning scored hits).
- Default embedder MUST be deterministic/offline (hashing/TF-IDF style). No remote embeddings.
- Metadata MUST include `path` (for ingested files) and `profile`; scoring semantics documented in retriever.
- RAG loader MUST validate backend at init; ingest MUST persist profile in metadata; search MUST return scores.
- Local fallback search MUST use whole-word matching with deterministic ranking.

## Coordinator Policy
- MUST use round-robin worker selection with thread-safety guarantees (lock-protected index increment).
- MUST ensure fairness across workers; preserve step ordering and trace aggregation.

## Configuration Policy
- Env parsing MUST be robust with defaults/fallbacks; clamp `PLANNER_MAX_STEPS` to 1..50 and `MODEL_TEMPERATURE` to 0..2.
- SHOULD emit warnings when env values are invalid and fall back to defaults.
- Config changes MUST update tests and docs in the same PR.

## Observability & Tracing
- Logs MUST be structured (JSON-friendly) and omit PII; redact secrets before emission.
- `trace_id` MUST propagate across planner/worker/coordinator, CLI, and tools.
- Emit events for plan creation, tool selection, execution start/stop, backend connections, and errors.

## Testing Invariants
- Tests MUST assert planner does not return all tools blindly; vector scores correlate with similarity and are ordered.
- Import guardrails MUST be enforced (reject non-`cuga.modular.tools.*`).
- Round-robin coordinator scheduling MUST be verified under concurrent calls.
- Env parsing tests MUST cover invalid/edge values and fallback behavior.
- AGENTS.md anchors (these sections) MUST be validated by guardrail tests.

## Change Management
- Edit `AGENTS.md` first when modifying guardrails; update `CHANGELOG.md` (`## vNext`) with summary.
- Any change violating or adjusting guardrails MUST update this file plus corresponding tests in the same PR.
- PRs MUST include tests, docs, and observability updates for affected areas.
