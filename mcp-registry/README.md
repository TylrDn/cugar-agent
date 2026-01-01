# MCP Registry

This directory contains YAML-driven registry files for MCP (Model Context Protocol) servers used by the CUGA agent.

## Overview

The MCP registry system provides a declarative way to define and manage MCP servers across different transport types:

- **HTTP Transport**: Remote MCP servers accessible via HTTP/HTTPS
- **Process Transport**: Local MCP servers launched as subprocesses
- **Embedded Transport**: MCP servers embedded within the cugar-agent repository

## Registry Files

### http.yaml

Defines remote MCP servers that communicate via JSON-RPC over HTTP/HTTPS. These servers typically run on external platforms like Pipedream or cloud services.

**Example entry:**
```yaml
servers:
  - name: example-server
    transport: http
    url: https://example.com/mcp
    capabilities:
      - action: read
        auth: token-required
        description: "Read data from service"
    permission_scope: read-only
    timeout: 30
    auth:
      type: bearer
      token_env: MCP_AUTH_TOKEN
```

### process.yaml

Defines local MCP servers that are launched as subprocesses and communicate via stdin/stdout using JSON-RPC.

**Example entry:**
```yaml
servers:
  - name: filesystem
    transport: stdio
    command: npx
    args:
      - "-y"
      - "@modelcontextprotocol/server-filesystem"
      - "./cuga_workspace"
    capabilities:
      - action: read
        description: "Read files"
      - action: write
        description: "Write files"
    permission_scope: read-write
    timeout: 30
    max_restarts: 3
```

### embedded.yaml

Defines MCP servers that are embedded within the cugar-agent repository and loaded as Python modules.

**Example entry:**
```yaml
servers:
  - name: embedded-calculator
    transport: embedded
    module: cuga.mcp_servers.calculator.server
    path: src/cuga/mcp_servers/calculator
    capabilities:
      - action: compute
        description: "Mathematical calculations"
    permission_scope: read-only
    sandbox:
      enabled: true
      allowed_operations:
        - "arithmetic"
    timeout: 10
```

## Registry Schema

### Common Fields

All server entries share these common fields:

- **name** (required): Unique identifier for the server
- **transport** (required): Transport type (`http`, `stdio`, or `embedded`)
- **capabilities** (required): List of capabilities provided by the server
  - **action**: The capability action (e.g., `read`, `write`, `compute`)
  - **auth**: Authentication requirement (`none`, `token-required`, `connection-required`)
  - **description**: Human-readable description
- **permission_scope** (required): Permission level (`read-only`, `read-write`, `execute`, `admin`)
- **timeout**: Request timeout in seconds (default: 30)

### HTTP-specific Fields

- **url**: Base URL of the MCP server
- **retry_policy**: Retry configuration
  - **max_retries**: Maximum number of retry attempts
  - **backoff_strategy**: `exponential` or `linear`
- **health_check**: Health check configuration
  - **enabled**: Enable health checks
  - **interval**: Check interval in seconds
  - **endpoint**: Health check endpoint path
- **auth**: Authentication configuration
  - **type**: Auth type (`bearer`, `basic`, etc.)
  - **token_env**: Environment variable containing the token

### Process-specific Fields

- **command**: Command to execute (e.g., `npx`, `python`, `node`)
- **args**: Command arguments as a list
- **working_dir**: Working directory for the subprocess
- **env**: Environment variables for the subprocess
- **startup_timeout**: Timeout for server startup in seconds
- **max_restarts**: Maximum number of restart attempts

### Embedded-specific Fields

- **module**: Python module path for the server
- **path**: Relative path to the server code within the repository
- **sandbox**: Sandbox configuration
  - **enabled**: Enable sandboxed execution
  - **allowed_paths**: List of allowed file paths
  - **forbidden_paths**: List of forbidden file paths
  - **allowed_operations**: List of allowed operation types
  - **forbidden_operations**: List of forbidden operation types
  - **max_input_size**: Maximum input size in bytes

## Usage

### Loading a Registry

```python
from src.mcp_clients import HttpMCPClient, ProcessMCPClient, EmbeddedMCPLoader
import yaml

# Load HTTP servers
with open('mcp-registry/http.yaml') as f:
    http_registry = yaml.safe_load(f)

# Create HTTP client
for server in http_registry['servers']:
    client = HttpMCPClient(
        base_url=server['url'],
        timeout=server.get('timeout', 30),
    )
```

### Using the Router

```python
from src.mcp_router import MCPRouter, MCPServerConfig, MCPCapability, AgentRequest, TransportType

# Create router
router = MCPRouter()

# Load and register servers from registry files
# (Implementation depends on your registry loader)

# Route a request
request = AgentRequest(
    intent="Read a file",
    category="filesystem",
    required_capabilities=["read"],
)

decision = router.route_request(request)
if decision:
    print(f"Routed to: {decision.server.name}")
```

## Best Practices

1. **Security**: Always use authentication for production servers
2. **Timeouts**: Set appropriate timeouts based on expected operation duration
3. **Health Checks**: Enable health checks for critical servers
4. **Sandboxing**: Use sandbox constraints for embedded servers
5. **Permission Scopes**: Follow principle of least privilege
6. **Documentation**: Provide clear descriptions for all capabilities

## Future Enhancements

- Dynamic server discovery
- Load balancing across multiple servers
- Automatic failover and retry strategies
- Runtime registry updates
- Telemetry and monitoring integration
