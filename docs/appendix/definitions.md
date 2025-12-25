# Definitions

- Tier 1: foundational integrations default-enabled for orchestration, execution, filesystem, web/search, and VCS; cataloged in `docs/mcp/registry.yaml` and surfaced in `docs/mcp/tiers.md`.
- Tier 2: optional integrations disabled by default (finance/CMS/social/DB/vector/observability); enabled via registry + compose profiles.
- Unrated: community/experimental plugins outside core; load only through external registry fragments.
- Sandbox Profile: resource + mount policy (see `docs/compute/sandboxes.md`) applied per tool.
- Tool: an external capability exposed via MCP/HTTP; must be declared in the registry.
- Adapter: implementation behind the ToolBus interface that speaks MCP/HTTP without leaking vendor SDKs into core.
- Registry: canonical map in `docs/mcp/registry.yaml` governing tiers, sandboxes, mounts, and env hooks; drives generated `docs/mcp/tiers.md`.
