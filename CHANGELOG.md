# 📦 CHANGELOG

All notable changes to the CUGAR Agent project will be documented in this file.
This changelog follows the guidance from [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

---

## vNext

### Added
- ➕ Added: Deterministic hashing embedder and pluggable vector backends with local search fallback.
- ➕ Added: Secure modular CLI for ingest/query/plan with trace propagation and JSON logs.
- ➕ Added: Guardrail checker and AGENTS.md SSOT for modular stack.
- ➕ Added: Modular `cuga.modular` package with planner/worker/tool/memory/observability scaffolding ready for LangGraph/LangChain
- ➕ Added: Vector memory abstraction with in-memory fallback and optional Chroma/Qdrant/Weaviate/Milvus connectors
- ➕ Added: LlamaIndex RAG loader/retriever utilities and Langfuse/OpenInference observability hooks
- ➕ Added: Developer tooling (.editorconfig, .gitattributes, pre-commit config, expanded Makefile) and CI workflow `ci.yml`
- ➕ Added: Templates and documentation for `.env`, roadmap, and multi-agent examples under `agents/`, `tools/`, `memory/`, and `rag/`
- In development: GitHub Actions CI, coverage reports, Langflow project inspector
- ➕ Added: `scrape_tweets` MCP tool using `snscrape` for Twitter/X scraping
- ➕ Added: `extract_article` MCP tool powered by `newspaper4k` style extraction
- ➕ Added: `crypto_wallet` MCP tool wrapper for mnemonic, derivation, and signing flows
- ➕ Added: `moon_agents` MCP tool exposing agent templates and plan scaffolds
- ➕ Added: `vault_tools` MCP tool bundle for JSON queries, KV storage, and timestamps
- ➕ Added: CLI for listing agents, running goals, and exporting structured results
- ➕ Added: External tool plugin system with discovery helpers and a template plugin example
- ➕ Added: Env-gated MCP registry loader/runner wiring with sample `registry.yaml` and planner/executor integration
- ➕ Added: Agent UI intent preview, invocation timeline, and state badge for clearer tool legibility
- ➕ Added: Expanded guardrail verification script (`scripts/verify_guardrails.py`), inheritance markers, and CI enforcement
- ➕ Added: Guardrail verifier coverage for allowlist/denylist, budget, escalation, and redaction keywords plus planner/worker/coordinator contracts
- ➕ Added: Dual-mode LLM adapter layer with hybrid routing, budget guardrails, and config/env precedence
- ➕ Added: Architecture/registry observability documentation set (overview, registry, tiers, sandboxes, compose, ADR, glossary)
- ➕ Added: MCP v2 registry slice with immutable snapshot models, YAML loader, and offline contract tests

### Changed
- 🔁 Changed: Planner, coordinator, worker, and RAG pipelines to enforce profile/trace propagation and round-robin fairness.
- 🔁 Changed: Dynamic tool imports hardened to `cuga.modular.tools.*` namespace with explicit errors.
- 🔁 Changed: Centralized MCP server utilities for payload handling and sandbox lookup
- 🔁 Changed: Planner now builds multi-step plans with cost/latency optimization, logging, and trace outputs
- 🔁 Changed: Controller and executor now emit structured audit traces and sanitize handler failures
- 🔁 Changed: Tool registry now deep-copies resolved entries and profile snapshots to prevent caller mutations from leaking between tools
- 🔁 Changed: Reconciled agent lifecycle, tooling, and security documentation with current code enforcement boundaries
- 🔁 Changed: Guardrail routing updated so root `AGENTS.md` remains canonical with per-directory inherit markers
- 🔁 Changed: Guardrail verification now centralizes allowlists/keywords and supports env overrides to reduce drift
- 🔁 Changed: Guardrail verification now tracks `config/` with inheritance markers to cover Hydra registry defaults
- 🔁 Changed: Root `AGENTS.md` reorganized to align Tier 1 defaults with registry tool swaps, sandbox pinning, and budget/redaction guardrails
- 🔁 Changed: Pytest default discovery now targets `tests/`, with docs/examples suites run through dedicated scripts and build artifacts ignored by default
- 🔁 Changed: Pytest `norecursedirs` now retains default exclusions (e.g., `.*`, `venv`, `dist`, `*.egg`) to avoid unintended test discovery
- 🔁 Changed: LLM adapter can run atop LiteLLM by default with hardened retries, fallback error handling, and thread-safe budget warnings
- 🔁 Changed: MCP registry loader now uses Hydra's `compose` API for Hydra/OmegaConf configuration composition with shared config defaults and fragment support

### Fixed
- 🐞 Fixed: Hardened `crypto_wallet` parameter parsing and clarified non-production security posture
- 🐞 Fixed: `extract_article` dependency fallback now respects missing `html` inputs
- 🐞 Fixed: `moon_agents` no longer returns sandbox filesystem paths
- 🐞 Fixed: `vault_tools` KV store now uses locked, atomic writes to avoid race conditions
- 🐞 Fixed: `vault_tools` detects corrupt stores, enforces locking support, and writes under held locks
- 🐞 Fixed: `vault_tools` KV store writes use fsynced temp files to preserve atomic persistence safety
- 🐞 Fixed: `_shared` CLI argument parsing now errors when `--json` is missing a value
- 🐞 Fixed: `crypto_wallet` narrows `word_count` parsing errors to expected types
- 🐞 Fixed: `_shared.load_payload` narrows JSON parsing exceptions for clearer diagnostics
- 🐞 Fixed: `extract_article` fallback parsing now only triggers for expected extraction or network failures
- 🐞 Fixed: Guardrail checker git diff detection now validates git refs and uses fixed git diff argv to avoid unchecked subprocess input
- 🐞 Fixed: Tier table generation now falls back to env keys for non-placeholder values to avoid leaking secrets in docs
- 🐞 Fixed: MCP registry loader enforces enabled-aware duplicate detection, method/path type validation (including `operation_id`), and environment variables that override disabled entries when set

### Documentation
- 📚 Rewrote README/USAGE/AGENTS/CONTRIBUTING/SECURITY with 2025 agent-stack guidance and integration steps
- 📚 Documented: Branch cleanup workflow and issue stubs for consolidating Codex branches
- 📚 Documented: Root guardrails, audit expectations, and routing table for guardrail updates
- 📚 Documented: Hydra-based registry composition (env overrides, enabled-only duplicate detection) and linked MCP integration guidance
- 📚 Documented: Refined canonical `AGENTS.md` with quick checklist, local template, and cross-links to policy docs
- 📚 Documented: Architecture topology (controller/planner/tool bus), orchestration modes, and observability enhancements
- 📚 Documented: STRIDE-lite threat model and red-team checklist covering sandbox escape, prompt injection, and leakage tests
- 📚 Documented: Usage and testing quick-start guides plus repository Code of Conduct and security policy

### Testing
- 🧪 Added: Unit tests for vector search scoring, planning relevance, round-robin dispatch, env parsing, and CLI flow.
- 🧪 Added: Expanded `scrape_tweets` test coverage for limits, dependencies, and health checks
- 🧪 Added: Offline MCP registry, runner, and planner/executor tests backed by FastAPI mock servers
- 🧪 Added: Dedicated lint workflow running Ruff and guardrail verification on pushes and pull requests

---

## [v1.0.0] - Initial Production Release

🎉 This is the first production-ready milestone for the `cugar-agent` framework.

### ✨ Added
- Modular agent pipeline:
  - `controller.py` – agent orchestration
  - `planner.py` – plan step generator
  - `executor.py` – tool execution
  - `registry.py` – tool registry and sandboxing
- Profile-based sandboxing with scoped tool isolation
- MCP-ready integrations and registry templating
- Profile fragment resolution logic (relative to profile path)
- PlantUML message flow for documentation
- Developer-friendly `Makefile` for env, profile, and registry tasks
- Initial tests in `tests/` for agent flow verification
- ➕ Added: Profile policy enforcer with schema validation and per-profile templates under `configurations/policies`

### 🛠️ Changed
- Standardized folder structure under `src/cuga/`
- Updated `.env.example` for MCP setup

### 📚 Documentation
- Rewritten `AGENTS.md` as central contributor guide
- Added structure for:
  - `agent-core.md`
  - `agent-config.md`
  - `tools.md`
- Registry merge guide in `docs/registry_merge.md`
- Security policy in `docs/Security.md`
- ➕ Added: `docs/policies.md` describing policy authoring and enforcement flow

### ⚠️ Known Gaps
- CLI runner may need test scaffolding
- Tool schema validation needs stronger contract enforcement
- Logging verbosity defaults may need hardening

---
