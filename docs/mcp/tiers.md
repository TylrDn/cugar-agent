Tier 1: mandatory defaults for foundational orchestration, execution, filesystem, web/search, VCS, and news/social tools. Always enabled in registry.yaml and wired in compose; sandboxed with least privilege.

Tier 2: optional extensions (finance/crypto, CMS/social, DB/vector, observability providers). Disabled by default; opt-in via compose profiles and registry toggle. Unrated: community plugins only, loaded via registry fragments outside core.

Integration matrix
| tool             | tier | registry id       | auth vars                  | sandbox profile | fs scope              | network | observability taps | status |
|------------------|------|-------------------|----------------------------|-----------------|----------------------|---------|--------------------|--------|
| Langflow         | 1    | langflow          | LANGFLOW_API_KEY           | n/a             | none                  | on      | TraceSink          | on     |
| ALTK             | 1    | altk              | ALTK_TOKEN                 | n/a             | none                  | on      | TraceSink          | on     |
| E2B MCP          | 1    | mcp.e2b           | E2B_API_KEY                | py-full         | /workdir rw           | on      | TraceSink          | on     |
| FileSystem MCP   | 1    | mcp.fs            | none                       | py-slim         | /workspace ro + out rw| off     | TraceSink          | on     |
| fast-filesystem  | 1    | mcp.fastfs        | none                       | py-slim         | /workspace ro + out rw| off     | TraceSink          | on     |
| llm-context      | 1    | mcp.llmcontext    | none                       | py-slim         | /workspace/output rw  | off     | TraceSink          | on     |
| FileStash        | 1    | mcp.filestash     | none                       | py-full         | /workspace/output rw  | on      | TraceSink          | on     |
| Backup MCP       | 1    | mcp.backup        | none                       | py-full         | /workspace/output rw  | on      | TraceSink          | on     |
| Browser MCP      | 1    | mcp.browser       | BROWSER_API_KEY optional   | node-full       | none                  | on      | TraceSink          | on     |
| Search MCP       | 1    | mcp.search        | SEARCH_API_KEY optional    | node-slim       | none                  | on      | TraceSink          | on     |
| snscrape         | 1    | mcp.snscrape      | none                       | py-full         | none                  | on      | TraceSink          | on     |
| newspaper4k      | 1    | mcp.newspaper     | none                       | py-full         | none                  | on      | TraceSink          | on     |
| Git CLI          | 1    | mcp.git           | none                       | py-slim         | /workspace/repos rw   | off     | TraceSink          | on     |
| GitHub           | 1    | mcp.github        | GITHUB_TOKEN               | py-slim         | none                  | on      | TraceSink          | on     |
| GitLab           | 1    | mcp.gitlab        | GITLAB_TOKEN               | py-slim         | none                  | on      | TraceSink          | on     |
| Gitingest        | 1    | mcp.gitingest     | none                       | py-slim         | none                  | on      | TraceSink          | on     |
| Phabricator      | 1    | mcp.phabricator   | PHAB_TOKEN optional        | py-slim         | none                  | on      | TraceSink          | on     |
| Crypto MCP       | 2    | mcp.crypto        | CRYPTO_API_KEY optional    | py-full         | none                  | on      | TraceSink          | off    |
| Finance MCP      | 2    | mcp.finance       | FIN_API_KEY optional       | py-full         | none                  | on      | TraceSink          | off    |
| WordPress MCP    | 2    | mcp.wordpress     | WP_TOKEN optional          | node-full       | none                  | on      | TraceSink          | off    |
| Social/content   | 2    | mcp.social        | none                       | node-full       | none                  | on      | TraceSink          | off    |
| SQL DB           | 2    | mcp.sqldb         | SQL_URL optional           | py-full         | /workspace/db rw      | on      | TraceSink          | off    |
| Vector DB        | 2    | mcp.vector        | VECTOR_URL optional        | py-full         | /workspace/vector rw  | on      | TraceSink          | off    |
| LangFuse         | 2    | observability.langfuse | LANGFUSE_PUBLIC_KEY/SECRET_KEY | n/a | none | on | TraceSink | off |
| LangSmith        | 2    | observability.langsmith | LANGCHAIN_API_KEY        | n/a             | none                  | on      | TraceSink          | off    |

Links: registry entries in docs/mcp/registry.yaml; sandbox profiles in docs/compute/sandboxes.md; observability settings in docs/observability/config.md.
