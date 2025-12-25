Assumptions (from current stack): Python 3.12+ orchestration with MCP registry/lifecycle and Langflow support in CUGA agent.​:codex-file-citation[codex-file-citation]{line_range_start=35 line_range_end=59 path=README.md git_url="https://github.com/TylrDn/cugar-agent/blob/main/README.md#L35-L59"}​​:codex-file-citation[codex-file-citation]{line_range_start=51 line_range_end=83 path=docs/MCP_INTEGRATION.md git_url="https://github.com/TylrDn/cugar-agent/blob/main/docs/MCP_INTEGRATION.md#L51-L83"}​

CUGAR orchestration (logical)
+-------------------+        control           +---------------------------+
| Langflow UI/ALTK  | -----------------------> | Agent Orchestrator (CUGA) |
+---------+---------+                          +------------+-------------+
          |                                               |
          |                                               v
          |                                   +-----------+------------+
          |                                   | Core Interfaces        |
          |                                   | - ToolBus              |
          |                                   | - StateStore           |
          |                                   | - VectorIndex          |
          |                                   | - TraceSink            |
          |                                   | - SecretStore          |
          |                                   | - ProfileRegistry      |
          |                                   +-----------+------------+
          |                                               |
          |                           +-------------------+-------------------+
          |                           | Tool Adapters (MCP bridge)            |
          |                           | - Execution MCP (E2B)                 |
          |                           | - File MCP (FileSystem/fast/llm/backup|
          |                           | - Web MCP (browser/search)            |
          |                           | - VCS MCP (Git/GitHub/GitLab/Phab)    |
          |                           | - News/social (snscrape/newspaper4k)  |
          |                           | - Optional Tier2 (DB/crypto/wp/...)   |
          |                           +-------------------+-------------------+
          |                                               |
          |                           +-------------------+-------------------+
          |                           | Sandboxes (Docker profiles)           |
          |                           | - py-slim/full, node-slim/full        |
          |                           | - FS mounts + network policies        |
          |                           +-------------------+-------------------+
          |                                               |
          |                           +-------------------+-------------------+
          |                           | Observability (OTEL/LangFuse/LangSmith|
          |                           | Metrics/traces via TraceSink          |
          |                           +-------------------+-------------------+
          |                                               |
          +--------------------------- state/traces <-----+
Data flow: request → Langflow/ALTK → Orchestrator (profile) → ToolBus → MCP adapter → sandboxed tool → responses → StateStore → TraceSink.
Control flow: policy/config resolve registry entry → launch per profile sandbox → enforce limits/observability → return results.

Core interfaces (replaceable modules)
- ToolBus: resolve tool id → call adapter (MCP/HTTP/native); enforces retries, timeouts, breakers.
- StateStore: conversation + artifact persistence (pluggable local/remote).
- VectorIndex: embeddings store; optional (Tier2).
- TraceSink: observability abstraction (OTEL/LangFuse/LangSmith).
- SecretStore: env/secret backend shim (no hardcoded secrets).
- ProfileRegistry: single source of truth from docs/mcp/registry.yaml, profile-aware.

State & config
- Single registry at docs/mcp/registry.yaml drives tool availability and sandbox hints.
- Sandboxes defined in docs/compute/sandboxes.md and wired via ops/docker-compose.proposed.yaml.
- Observability defaults in docs/observability/config.md.
