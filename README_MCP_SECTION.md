## MCP Integration Quick Start

CUGAR now supports the Model Context Protocol (MCP) for loading 1,500+ external tools with enterprise-grade security.

### Features

- **Tier-Based Security**: Tools are categorized into tiers (1: sandbox, 2: restricted, 3: trusted)
- **Guard Enforcement**: Every tool invocation passes through guard checks
- **Audit Logging**: Append-only JSONL audit trail with cost/latency tracking
- **Deterministic**: Stable tool ordering and normalized outputs for reproducible tests
- **Langflow Integration**: Visual workflow design with MCP tools

### Quick Usage

```python
from cuga.tools.mcp_toolbox import create_mcp_toolbox

# Load MCP tools with tier 1 (sandbox) only
toolbox = create_mcp_toolbox(allowed_tiers=[1])

# Execute a tool
result = toolbox.execute_tool(
    tool_id="mcp.github",
    input={"action": "list_repos", "user": "TylrDn"},
    context={"trace_id": "demo123"}
)
```

### Make Targets

```bash
# Run all MCP tests
make test-mcp

# Run GitHub demo
make demo-mcp-github
```

### File Structure

- `src/cuga/tools/mcp_registry.py` - Registry loader with tier enforcement
- `src/cuga/tools/mcp_toolbox.py` - Guarded tool wrapper
- `src/cuga/observability/mcp_audit.py` - Audit logger
- `src/cuga/agents/executor.py` - Executor integration
- `src/cuga/langflow_components/mcp_client.py` - Langflow component
- `docs/mcp/registry.yaml` - Tool registry definition
- `examples/langflow/mcp_github_flow.json` - Demo flow
