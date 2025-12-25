# MCP Tiers

Tier 1 integrations are foundational and default-on; Tier 2 integrations are optional and default disabled. Unrated entries cover community plugins and are never enabled by default.

The integration matrix below is generated from `docs/mcp/registry.yaml` to avoid drift. See `../compute/sandboxes.md` for sandbox profiles and `../observability/config.md` for telemetry env keys.

| tool | tier | registry id | auth env vars | sandbox profile | fs scope | network | observability taps | status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ALTK Planner | Tier 1 | altk | ALTK_HOST | node-full | - | - | - | enabled |
| Backup MCP | Tier 1 | mcp.backup | - | py-full | /workspace/backups:/workspace/backups:rw | - | - | enabled |
| Browser MCP | Tier 1 | mcp.browser | BROWSER_BASE_URL | node-full | - | - | - | enabled |
| Docker MCP Sandbox | Tier 1 | mcp.docker | - | py-full | /var/run/docker.sock:/var/run/docker.sock:ro | - | - | enabled |
| E2B MCP Sandbox | Tier 1 | mcp.e2b | E2B_API_KEY | py-full | /workspace:/workdir:rw | - | - | enabled |
| Fast FileSystem MCP | Tier 1 | mcp.fast-fs | - | py-slim | /workspace:/workspace:ro, /workspace/cache:/workspace/cache:rw | - | - | enabled |
| FileStash MCP | Tier 1 | mcp.filestash | - | py-full | /workspace/storage:/workspace/storage:rw | - | - | enabled |
| FileSystem MCP | Tier 1 | mcp.fs | - | py-slim | /workspace:/workspace:ro, /workspace/artifacts:/workspace/artifacts:rw | - | - | enabled |
| Git CLI MCP | Tier 1 | mcp.git | - | py-slim | /workspace/repos:/workspace/repos:ro | - | - | enabled |
| GitHub MCP | Tier 1 | mcp.github | GITHUB_TOKEN | py-slim | /workspace/repos:/workspace/repos:ro | - | - | enabled |
| Gitingest MCP | Tier 1 | mcp.gitingest | - | py-slim | /workspace/repos:/workspace/repos:ro | - | - | enabled |
| GitLab MCP | Tier 1 | mcp.gitlab | GITLAB_TOKEN | py-slim | /workspace/repos:/workspace/repos:ro | - | - | enabled |
| Langflow Control Plane | Tier 1 | langflow | LANGFLOW_HOST | node-full | - | - | - | enabled |
| LLM Context MCP | Tier 1 | mcp.llm-context | - | py-slim | /workspace/context:/workspace/context:rw | - | - | enabled |
| Newspaper4k MCP | Tier 1 | mcp.newspaper | - | py-full | - | - | - | enabled |
| Phabricator MCP | Tier 1 | mcp.phabricator | PHABRICATOR_TOKEN | py-slim | /workspace/repos:/workspace/repos:ro | - | - | enabled |
| Search MCP | Tier 1 | mcp.search | - | node-slim | - | - | - | enabled |
| snscrape MCP | Tier 1 | mcp.snscrape | - | py-full | /workspace/social:/workspace/social:rw | - | - | enabled |
| LangFuse | Tier 2 | langfuse | LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY | py-slim | - | - | - | disabled |
| LangSmith | Tier 2 | langsmith | LANGCHAIN_API_KEY | py-slim | - | - | - | disabled |
| Observability Exporter | Tier 2 | observability | - | py-slim | - | - | - | disabled |
| Scheduler / DAG MCP | Tier 2 | scheduler | - | py-full | /workspace/schedules:/workspace/schedules:rw | - | - | disabled |
| Vector DB MCP | Tier 2 | vector-db | VECTOR_DB_URL | py-full | /workspace/vector:/workspace/vector:rw | - | - | disabled |
