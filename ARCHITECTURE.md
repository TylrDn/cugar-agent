# Architecture Overview

## Modular Stack
- Planner → Coordinator → Workers with profile-scoped VectorMemory.
- Embeddings: deterministic hashing embedder; vector backends (FAISS/Chroma/Qdrant) behind `VectorBackend` protocol.
- RAG: RagLoader validates backends at init and persists `path`/`profile` metadata; RagRetriever surfaces scored hits.

## Scheduling & Execution
- PlannerAgent ranks tools by goal similarity (ReAct/Plan-and-Execute hybrid) respecting config max steps.
- CoordinatorAgent dispatches workers via thread-safe round-robin to guarantee fairness.
- WorkerAgent defaults profile to memory profile, propagates `trace_id`, and logs structured traces.

## Tooling & CLI
- ToolRegistry restricts dynamic imports to `cuga.modular.tools.*`.
- CLI (`python -m cuga.modular.cli`) provides `ingest`, `query`, `plan` with JSON logs and shared state file for demos.

## Governance
- AGENTS.md + `scripts/guardrails_check.py` act as the code-as-policy layer; CI/tests enforce required anchors/phrases.
- Guardrail changes must co-evolve with tests and the checker to remain the authoritative source for safety and planning rules.
- Long-term evolution follows changelog entries and migration notes so downstream agents can adapt without regressions.
