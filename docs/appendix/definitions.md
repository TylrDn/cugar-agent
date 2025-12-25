# Definitions

- **Tier 1:** Foundational integrations, default enabled; see `docs/mcp/tiers.md`.
- **Tier 2:** Optional integrations, default disabled; enable via registry and compose profiles.
- **Unrated:** Community or experimental plugins; never default-on.
- **Sandbox Profile:** Resource + policy bundle selecting the compose service; see `docs/compute/sandboxes.md`.
- **Tool:** A callable capability exposed via MCP or HTTP.
- **Adapter:** An implementation that binds a tool to the core interfaces and sandbox profile.
- **Registry:** Canonical list of tools, profiles, and defaults at `docs/mcp/registry.yaml`.
