# 🧭 Root Guardrails (Canonical)

This root `AGENTS.md` is the **canonical authority** for the entire repository. All directories inherit these guardrails by default; any local `AGENTS.md` may only add stricter rules. If a local rule conflicts with this file, **this file wins**. Escalate unresolved conflicts to the codeowners or the security reviewer before merging.

---

## 1. Scope & Precedence
- Root guardrails apply to every profile, tool, workflow, and document in this repo.
- Local `AGENTS.md` files must start with: `This directory inherits from root \`AGENTS.md\` (canonical). Conflicts resolve to root.`
- Conflict resolution order: **root → nearest directory AGENTS.md → implicit inherit markers**.
- If a rule is ambiguous, pause the change, document the ambiguity in the PR, and request a maintainer review.

## 2. Profile Isolation
- Treat each profile as a hard boundary: tools, caches, and runtime state **must not** cross between profiles.
- Disable or re-scope any shared handles that could leak state (file handles, sockets, process-wide caches).
- Profile-local memory: keep replay buffers, traces, and registries scoped by profile ID.
- No cross-profile filesystem writes or reads unless explicitly whitelisted and documented.
- Review checklist before merging:
  - [ ] Do tools run only with their profile-scoped registry?
  - [ ] Are in-memory caches keyed by profile and cleared on teardown?
  - [ ] Are profile artefacts written to sandbox-specific paths?

## 3. Registry Hygiene
- Registry fragments must be deep-copied before merge; callers must never see shared references.
- Merge order is deterministic: profile base → ordered fragments → overrides; later entries win only after conflict validation.
- Name/version rules: use `<domain>.<capability>.<variant>:<semver>` to avoid collisions; bump on any breaking registry change.
- Conflicts fail fast with explicit file + key references; never silently overwrite.
- Ownership: registry format and merge semantics require approval from a registry maintainer.

## 4. Sandbox Expectations
- Sandboxed execution means: filesystem writes confined to the run directory, no implicit network access, and bounded resources (respect CI/container limits).
- Prohibited: background daemons, long-lived listeners, cross-profile IPC, and caching outside the sandbox.
- If a task needs expanded permissions, document the justification in the PR and add a temporary guard with TODO + owner.
- Assume non-production posture: remind users when examples or demos lack production hardening.

## 5. Audit / Trace Semantics
- Emit trace events for: plan creation, tool selection, tool invocation start/stop, registry merge results, and sanitization steps.
- Preserve ordering within a correlation ID; include monotonic timestamps and step indexes.
- Correlation IDs: generate per user request or job; propagate through controller → planner → executor.
- Redact secrets, tokens, and PII at emission time. Do not write raw secrets to logs or exports.
- Storage/export: keep traces local to the sandbox by default; if exporting, document retention, scope, and redaction.

## 6. Documentation Update Rules
- **No undocumented behavior changes.** Every behavior, guardrail, audit, CI, or safety change must update `CHANGELOG.md` under `## vNext`.
- Commit messages: prefer `[vX.Y.Z] {CHANGE_TYPE}: {SUMMARY}` for traceability.
- PR checklist (must appear in description):
  - [ ] Updated relevant AGENTS.md files and routing markers
  - [ ] Updated CHANGELOG.md `vNext`
  - [ ] Added/updated tests for guardrails or safety-sensitive code
  - [ ] Confirmed audit/trace redaction where applicable
- Documentation routing — if you change **X**, also update **Y**:
  - Guardrails → root/affected `AGENTS.md`, `CHANGELOG.md`, `.github/workflows/guardrails.yml`
  - Tool Registry semantics → `docs/registry*.md`, `AGENTS.md`, `scripts/verify_guardrails.py`
  - Audit/Trace → `docs/audit_and_trace.md`, `SECURITY.md`, CI retention notes
  - Profiles → `docs/profiles.md`, profile manifests, `AGENTS.md`
  - CI or safety policy → CI workflow files, `docs/tool_safety.md`, `SECURITY.md`, `CHANGELOG.md`

## 7. Verification & No Conflicting Guardrails
- Run `python scripts/verify_guardrails.py` (optionally `--base <git-ref>`) before committing.
- CI enforces these checks via `.github/workflows/guardrails.yml` and blocks merges on failures.
- No file other than this root document may claim to be canonical. Local `AGENTS.md` files may only declare inheritance and stricter deltas.
- If the checker or CI flags a gap, fix the guardrail or the routing marker before merge.

---

## Definitions & Limits
- **Sandbox**: ephemeral workspace with constrained resources and no implicit network access after setup.
- **Profile**: configuration bundle describing allowed tools and registries for a goal.
- **Registry fragment**: structured document merged into a profile-scoped registry.
- These guardrails constrain repository behavior only; they are not a full security model for production deployments.
