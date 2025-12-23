# Controller-led multi-agent architecture

This repository separates orchestration into controller, planner, executor, and registry layers to keep subagents isolated and tool-aware.

## Components
- **Controller (`src/cuga/agents/controller.py`)** – entrypoint that prepares profile-scoped registries, coordinates planning, and records execution context.
- **Planner (`src/cuga/agents/planner.py`)** – turns a goal into `PlanStep` tasks. Swap this out to change planning strategies without touching execution.
- **Executor (`src/cuga/agents/executor.py`)** – runs plan steps with sandboxed tools and returns structured `ExecutionResult` objects.
- **Registry (`src/cuga/agents/registry.py`)** – profiles tools, enforces conflict-free merges, and exposes `sandbox(profile)` to avoid cross-talk.

## Extending tools
- Register tools per profile with `ToolRegistry.register(profile, name, handler, config=...)`.
- Use `ToolRegistry.merge` to combine registries and detect conflicts.
- Keep handlers pure: accept `(input, config, context)` and return structured data for downstream steps.

## Isolation checklist
- Keep shared state out of handlers; pass needed context through `ExecutionContext.metadata`.
- Prefer new registry instances per profile (`sandbox`) instead of mutating shared registries.
- Use profile-aware environment configuration (see `docs/registry_merge.md`) to keep prod/test services separate.

## Orchestration flow
1. Build or load a `ToolRegistry` for the chosen profile.
2. Instantiate `Controller(planner, executor, registry)`.
3. Call `Controller.run(goal, profile, metadata={...})`.
4. Inspect `ExecutionResult.steps` for auditability and `ExecutionResult.output` for the final payload.

See `Agents.md` for high-level guardrails and documentation links.
