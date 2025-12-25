
# 📦 CHANGELOG

All notable changes to the CUGAR Agent project will be documented in this file.

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

## [vNext]
- In development: GitHub Actions CI, coverage reports, Langflow project inspector
- ➕ Added: `scrape_tweets` MCP tool using `snscrape` for Twitter/X scraping
- ➕ Added: `extract_article` MCP tool powered by `newspaper4k` style extraction
- ➕ Added: `crypto_wallet` MCP tool wrapper for mnemonic, derivation, and signing flows
- ➕ Added: `moon_agents` MCP tool exposing agent templates and plan scaffolds
- ➕ Added: `vault_tools` MCP tool bundle for JSON queries, KV storage, and timestamps
- 🔁 Changed: Centralized MCP server utilities for payload handling and sandbox lookup
- 🐞 Fixed: Hardened `crypto_wallet` parameter parsing and clarified non-production security posture
- 🐞 Fixed: `extract_article` dependency fallback now respects missing `html` inputs
- 🐞 Fixed: `moon_agents` no longer returns sandbox filesystem paths
- 🐞 Fixed: `vault_tools` KV store now uses locked, atomic writes to avoid race conditions
- 🐞 Fixed: `vault_tools` detects corrupt stores, enforces locking support, and writes under held locks
- 🐞 Fixed: `extract_article` fallback parser only activates when HTML is provided, avoiding masked network errors
- 🐞 Fixed: `_shared` CLI argument parsing now errors when `--json` is missing a value
- 🐞 Fixed: `crypto_wallet` narrows `word_count` parsing errors to expected types
- 🧪 Added: Expanded `scrape_tweets` test coverage for limits, dependencies, and health checks
- 🐞 Fixed: `vault_tools` KV store writes use fsynced temp files to preserve atomic persistence safety
- 🐞 Fixed: `_shared.load_payload` narrows JSON parsing exceptions for clearer diagnostics
- 🐞 Fixed: `extract_article` fallback parsing now only triggers for expected extraction or network failures
- 🐞 Fixed: Tool registry now deep-copies resolved entries and profile snapshots to prevent caller mutations from leaking between tools
- ➕ Added: CLI for listing agents, running goals, and exporting structured results
- ➕ Added: External tool plugin system with discovery helpers and a template plugin example
- 🔁 Changed: Planner now builds multi-step plans with cost/latency optimization, logging, and trace outputs

---
