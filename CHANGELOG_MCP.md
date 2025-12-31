## [Unreleased] - MCP Native Integration

### Added - MCP Native Enterprise Integration
- **MCP Tool Registry** (`src/cuga/tools/mcp_registry.py`): Load and manage 1,500+ MCP tools with tier-based security
  - Tier 1 (sandbox), Tier 2 (restricted), Tier 3 (trusted) classification
  - Deny-by-default security model
  - Deterministic tool ordering and stable sorting
- **MCP Toolbox** (`src/cuga/tools/mcp_toolbox.py`): Guarded tool execution wrapper
  - Guard enforcement before every tool invocation
  - Tier-based filtering
  - Deterministic tool loading and ordering
- **MCP Audit Logger** (`src/cuga/observability/mcp_audit.py`): Append-only JSONL audit trail
  - Cost tracking and latency metrics
  - Sensitive field redaction (tokens, secrets, passwords)
  - Output normalization for deterministic tests
- **Executor Integration** (`src/cuga/agents/executor.py`): MCP tool support in executor
  - MCP tools identified by "mcp." prefix
  - Backward compatible with existing standard tools
  - Guard enforcement and audit logging for all MCP invocations
- **Langflow Component** (`src/cuga/langflow_components/mcp_client.py`): Visual MCP integration
  - Load MCP tools in Langflow workflows
  - Configurable tier filtering
  - Statistics and tool listing
- **Demo Flow** (`examples/langflow/mcp_github_flow.json`): GitHub MCP integration example
- **Test Fixtures** (`tests/data/mcp_deterministic/`): Reproducible test data
- **Makefile Targets**: `test-mcp`, `demo-mcp-github`, `mcp-server`

### Tests
- 86+ comprehensive tests across all MCP modules
  - 22 registry tests
  - 25 toolbox tests
  - 16 executor integration tests
  - 13 Langflow component tests
  - 6 determinism tests
  - 7 roundtrip idempotence tests

### Security
- Deny-by-default tool loading
- Guard checks before every tool invocation
- Sensitive field redaction in audit logs
- Tier-based access control

### Documentation
- MCP Quick Start guide
- Integration examples
- API documentation for all MCP modules

---

