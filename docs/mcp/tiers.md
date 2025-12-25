Tier 1: foundational defaults for orchestration, execution, filesystem, web/search, and VCS. Registry-driven, default enabled.
Tier 2: optional extensions (finance/CMS/social/DB/vector/observability), default disabled. Unrated = community/experimental only.

Integration matrix (source of truth: docs/mcp/registry.yaml; sandboxes in docs/compute/sandboxes.md; observability in docs/observability/config.md)
| tool | tier | registry id | auth env vars | sandbox profile | fs scope | network | observability taps | status |
|------|------|-------------|---------------|-----------------|---------|---------|--------------------|--------|
| Altk | 1 | altk | ALTK_TOKEN | orchestrator | none | on | TraceSink | on |
| Langflow | 1 | langflow | LANGFLOW_API_KEY | orchestrator | none | on | TraceSink | on |
| Mcp Backup | 1 | mcp.backup | none | py-full | /workspace/output:rw | on | TraceSink | on |
| Mcp Browser | 1 | mcp.browser | BROWSER_API_KEY | node-full | none | on | TraceSink | on |
| Mcp Docker | 1 | mcp.docker | none | py-full | /workdir:ro; /workdir/output:rw | on | TraceSink | on |
| Mcp E2b | 1 | mcp.e2b | E2B_API_KEY | py-full | /workdir:ro; /workdir/output:rw | on | TraceSink | on |
| Mcp Fastfs | 1 | mcp.fastfs | none | py-slim | /workspace:ro; /workspace/output:rw | on | TraceSink | on |
| Mcp Filestash | 1 | mcp.filestash | none | py-full | /workspace/output:rw | on | TraceSink | on |
| Mcp Fs | 1 | mcp.fs | none | py-slim | /workspace:ro; /workspace/output:rw | on | TraceSink | on |
| Mcp Git | 1 | mcp.git | none | py-slim | /workspace/repos:rw | on | TraceSink | on |
| Mcp Github | 1 | mcp.github | GITHUB_TOKEN | py-slim | none | on | TraceSink | on |
| Mcp Gitingest | 1 | mcp.gitingest | none | py-slim | /workspace/repos:ro | on | TraceSink | on |
| Mcp Gitlab | 1 | mcp.gitlab | GITLAB_TOKEN | py-slim | none | on | TraceSink | on |
| Mcp Llmcontext | 1 | mcp.llmcontext | none | py-slim | /workspace/output:rw | on | TraceSink | on |
| Mcp Newspaper | 1 | mcp.newspaper | none | py-full | none | on | TraceSink | on |
| Mcp Phabricator | 1 | mcp.phabricator | PHAB_TOKEN | py-slim | none | on | TraceSink | on |
| Mcp Search | 1 | mcp.search | SEARCH_API_KEY | node-slim | none | on | TraceSink | on |
| Mcp Snscrape | 1 | mcp.snscrape | none | py-full | none | on | TraceSink | on |
| Mcp Crypto | 2 | mcp.crypto | CRYPTO_API_KEY | py-full | none | on | TraceSink | off |
| Mcp Finance | 2 | mcp.finance | FIN_API_KEY | py-full | none | on | TraceSink | off |
| Mcp Social | 2 | mcp.social | none | node-full | none | on | TraceSink | off |
| Mcp Sqldb | 2 | mcp.sqldb | SQL_URL | py-full | /workspace/db:rw | on | TraceSink | off |
| Mcp Vectordb | 2 | mcp.vectordb | VECTOR_URL | py-full | /workspace/vector:rw | on | TraceSink | off |
| Mcp Wordpress | 2 | mcp.wordpress | WP_TOKEN | node-full | /workspace/output:rw | on | TraceSink | off |
| Observability Langfuse | 2 | observability.langfuse | LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY | orchestrator | none | on | TraceSink/Export | off |
| Observability Langsmith | 2 | observability.langsmith | LANGCHAIN_API_KEY, LANGCHAIN_PROJECT | orchestrator | none | on | TraceSink/Export | off |
