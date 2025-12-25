# ADR 0005: Interfaces-first registry-driven integrations

## Status
Proposed

## Context
CUGA now integrates MCP and external tools via registry-driven orchestration. Root guardrails require deterministic registry merges and sandbox isolation.​:codex-file-citation[codex-file-citation]{line_range_start=17 line_range_end=42 path=AGENTS.md git_url="https://github.com/TylrDn/cugar-agent/blob/main/AGENTS.md#L17-L42"}​​:codex-file-citation[codex-file-citation]{line_range_start=15 line_range_end=124 path=docs/MCP_INTEGRATION.md git_url="https://github.com/TylrDn/cugar-agent/blob/main/docs/MCP_INTEGRATION.md#L15-L124"}​

## Decision
- Core communicates through small interfaces (ToolBus, StateStore, VectorIndex, TraceSink, SecretStore, ProfileRegistry). No vendor-specific calls in core.
- docs/mcp/registry.yaml is the single source of truth for tool availability, tiers, sandboxes, and env hooks.
- Tier 1 integrations are enabled by default; Tier 2 integrations remain opt-in via compose profiles and registry flags.
- Observability/budget controls live in env-driven settings (see docs/observability/config.md).

## Consequences
- Adding a tool requires implementing an adapter behind interfaces and a registry entry; core code remains unchanged.
- Operators can hot-swap tools by editing registry.yaml and reloading without code changes.
- Profiles remain isolated; sandboxes and mounts are explicit and least-privilege.
