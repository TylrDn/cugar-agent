# Repository To-Do (Comprehensive)

## Governance & Guardrails
- Align root `AGENTS.md` guardrails with current tool allowlist/denylist, escalation ceilings, redaction rules, and budget caps before enabling Tier 1 defaults.
- Add automated guardrail verification for any new planner/worker/coordinator interfaces and update tests accordingly.
- Document any adjustments to guardrails in `CHANGELOG.md` under `## vNext` alongside test updates.
- Keep README, PRODUCTION readiness notes, and security docs synchronized with guardrail and registry expectations; capture new follow-ups in this list whenever guardrails shift.

## Registry & Sandbox Enablement
- Complete Tier 1 registry composition so `docs/mcp/registry.yaml` matches compose service mounts/env with health checks.
- Enforce sandbox profiles (py/node slim/full) per registry entry, including read-only mounts and `/workdir` pinning for E2B/Docker execution.
- Wire observability and budget enforcement env keys (AGENT_*, OTEL, LangFuse/LangSmith) with `warn|block` budget policies and trace sampling controls.
- Publish Tier 2 optional modules marked `enabled: false`, ensuring compose `tier2` profile launches optional observability/vector DB services with documented network limits.
- Add registry-driven hot-swap flow so tool replacements occur via registry edits only; auto-regenerate doc tables; add deterministic sort tests.

## Planner, Coordinator, and Tooling
- Finalize LangGraph-first planner/executor wiring with streaming callbacks and structured trace propagation.
- Ensure coordinator uses thread-safe round-robin worker selection with preserved plan ordering under concurrency.
- Harden tool import guardrails to restrict dynamic imports to `cuga.modular.tools.*` and enforce parameter declarations with explicit IO expectations.
- Expand tool selection logic to avoid blindly selecting all tools and to rank candidates by description/name similarity; verify via tests.
- Standardize a lightweight developer checklist (in README/AGENTS) for planner/worker/registry changes that references guardrail verification and required tests.

## Memory, RAG, and Embeddings
- Harden vector memory connectors with async batching, retention policies, and backend validation at initialization.
- Ensure metadata for ingested content always includes `path` and `profile`; document scoring semantics and deterministic local fallback search.
- Confirm default embedder remains deterministic/offline (hashing/TF-IDF) and disallows remote embeddings unless explicitly permitted.

## Observability & Tracing
- Ship default Langfuse/OpenInference dashboards and Traceloop spans for registry, planning, and execution paths.
- Emit structured, PII-free logs with secret redaction and full `trace_id` propagation across planner/worker/coordinator, CLI, and tools.
- Instrument events for plan creation, tool selection, execution start/stop, backend connections, errors, and budget decisions.
- Add guardrail verification to observability dashboards (or runbooks) so operators can track budget ceiling/escalation events and registry allowlist violations.

## Deployment & API Profiles
- Add FastAPI LangServe-style deployment profile for hosted APIs with secure defaults and budget controls.
- Provide first-party compose profile for hosted APIs with health checks and rollback guidance.

## Integrations & Adapters
- Build CrewAI/AutoGen adapters that honor coordinator/worker patterns and shared memory semantics.
- Develop long-running planning mode inspired by Strands/Semantic Kernel for job orchestration.

## Frontend & Workspace
- Polish frontend workspace/dashboard bundles to expose registry status, budgets, and trace timelines.
- Ensure embedded asset pipeline stays deterministic and documented (compression ratios, hashing).

## Testing & Stability
- Raise functional test coverage to at least 80% and extend regression/eval harness for self-play and MCP registry conformance.
- Maintain CI guardrail script (`scripts/verify_guardrails.py`), lint (`ruff`) checks, and stability tests in `run_stability_tests.py`.

## Release Engineering
- Prepare tagging and release automation aligned to `VERSION.txt` and `CHANGELOG.md` updates.
- Keep migration notes current for any breaking changes across MCP runners, registry behaviors, or sandbox policies.
