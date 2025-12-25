# ADR 0005: Interfaces-First Registry

## Status
Proposed

## Context
The agent platform must stay orchestration-agnostic while using Langflow + ALTK as the control plane. Vendor SDKs must remain outside core; adapters communicate via MCP and are governed by a single registry.

## Decision
- Define and stabilize core interfaces (`ToolBus`, `StateStore`, `VectorIndex`, `TraceSink`, `SecretStore`, `ProfileRegistry`).
- Treat `docs/mcp/registry.yaml` as the single source of truth. Compose, tiers docs, and runtime flags are derived from it.
- Tier 1 integrations are default-on; Tier 2 integrations are opt-in via registry `enabled: false` and compose profiles.
- Observability and budget enforcement are fully env-driven to avoid code drift.

## Consequences
- New integrations must land as registry entries with matching sandbox profiles before compose changes.
- Breaking registry changes require version bumps and guardrail review.
- Hot-swapping integrations is possible by flipping registry entries and rerunning the doc generator.
