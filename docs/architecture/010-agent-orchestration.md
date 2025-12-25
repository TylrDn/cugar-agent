# Agent Orchestration (Langflow + ALTK)

## Orchestration Modes
- **Single-agent flow**: Langflow node resolves registry → MCP adapter → executes single tool with sandbox hints.
- **Hub-and-spoke**: Planner acts as controller, routing tasks to specialized tool agents; spokes advertise capability tags (e.g., `web.fetch`, `vcs.read`, `vector.query`).
- **Human-in-the-loop (HITL)**: Langflow pause/resume nodes combined with ALTK lifecycle checkpoints; prompts capture rationale, constraints, and approval notes.
- **Delegated execution**: Profile-scoped workers pull jobs tagged by capability and profile; registry fragments specify allowed MCP servers per worker class.

## Composition Patterns
1. **Registry Loader → Tool Resolver (MCP) → Planner (LLM) → Executor (ALTK) → Memory Writer** (FileSystem/llm-context).
2. **Tool Bus mediation**: deterministic registry merge, sandbox selection (E2B primary, Docker fallback), and audit hook insertion before MCP invocation.
3. **Safe fallbacks**: retries with jitter, cached responses for idempotent reads, and graceful degradation to read-only paths when write scopes are absent.

## Prompt and Tool Boundaries
- Prompts express goals, constraints, and safety rails; tools expose typed contracts and expected side effects.
- Registry URIs remain versioned (`<domain.capability.variant:semver>`); planners must request explicit variants when crossing profiles.
- Output schemas remain stable; breaking changes require registry version bumps and migration guides.

## Failure Handling and Tracing
- Timeouts + bounded retries per MCP call; circuit breakers at lifecycle layer.
- Correlation ID and OTEL span propagation: `controller → planner → registry merge → sandbox runner → tool result`.
- Error surfaces include registry conflicts, sandbox policy violations, and tool-level failures; each emits structured audit entries.
