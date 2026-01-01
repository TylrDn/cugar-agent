# MCP Clients

This package provides client implementations for different MCP (Model Context Protocol) server transports.

## Overview

The MCP client abstractions enable the CUGA agent to communicate with MCP servers across different transport mechanisms:

- **HTTP Client**: JSON-RPC over HTTP for remote servers
- **Process Client**: Subprocess-based stdio JSON-RPC for local servers
- **Embedded Loader**: Direct module loading for embedded servers

## Components

### HttpMCPClient

A JSON-RPC over HTTP client for communicating with remote MCP servers (e.g., Pipedream-hosted servers).

**Features:**
- Token injection via `.env.mcp`
- Dynamic tool discovery
- Structured timeout and retry mechanisms (exponential backoff)
- Comprehensive error handling
- Health check support

**Example Usage:**
```python
from mcp_clients import HttpMCPClient

# Initialize client
async with HttpMCPClient(
    base_url="https://example.com/mcp",
    timeout=30.0,
    max_retries=3,
    auth_token="your-token",
) as client:
    # Discover available tools
    tools = await client.discover_tools()
    print(f"Found {len(tools)} tools")
    
    # Call a tool
    result = await client.call_tool(
        "example_tool",
        {"param": "value"},
    )
    print(f"Result: {result}")
    
    # Health check
    is_healthy = await client.health_check()
    print(f"Server healthy: {is_healthy}")
```

### ProcessMCPClient

A subprocess manager for launching and communicating with local MCP servers via stdio JSON-RPC.

**Features:**
- Auto-restart on failure (configurable retry limit)
- Health checks and monitoring
- Sandboxed execution
- Structured timeout and error handling
- Graceful shutdown with SIGTERM/SIGKILL

**Example Usage:**
```python
from mcp_clients import ProcessMCPClient

# Initialize client
async with ProcessMCPClient(
    command="npx",
    args=["-y", "@modelcontextprotocol/server-filesystem", "./workspace"],
    timeout=30.0,
    max_restarts=3,
) as client:
    # Discover available tools
    tools = await client.discover_tools()
    print(f"Found {len(tools)} tools")
    
    # Call a tool
    result = await client.call_tool(
        "read_file",
        {"path": "test.txt"},
    )
    print(f"File content: {result}")
    
    # Check health
    is_healthy = client.is_healthy()
    print(f"Process healthy: {is_healthy}")
```

### EmbeddedMCPLoader

A loader for embedded MCP servers defined within the cugar-agent repository.

**Features:**
- Manifest-based server definitions
- Permission scope enforcement (read-only, read-write, execute, admin)
- Sandboxed execution within repository
- Dynamic discovery of available servers
- Security checks (path validation, permission hierarchy)

**Example Usage:**
```python
from mcp_clients import EmbeddedMCPLoader
from pathlib import Path

# Initialize loader
loader = EmbeddedMCPLoader(
    repo_root=Path("/path/to/cugar-agent"),
    manifest_file="mcp_servers_manifest.yaml",
)

# Load manifest
servers = loader.load_manifest()
print(f"Loaded {len(servers)} servers")

# Get server details
server = loader.get_server("embedded-calculator")
print(f"Server path: {server['path']}")
print(f"Permission scope: {server['permission_scope']}")

# Check permissions
if loader.check_permission("embedded-calculator", "read-only"):
    # Load and use the server
    module = loader.load_server_module("embedded-calculator")
```

## Manifest Format

Embedded servers are defined in a YAML manifest file (`mcp_servers_manifest.yaml`):

```yaml
servers:
  example-server:
    path: mcp_servers/example
    module: cuga.mcp_servers.example.server
    permission_scope: read-write
    capabilities:
      - capability.action
    description: "Example server description"
```

**Required Fields:**
- `path`: Relative path to server code (must be within repository)
- `permission_scope`: One of `read-only`, `read-write`, `execute`, `admin`

**Optional Fields:**
- `module`: Python module path for dynamic import
- `capabilities`: List of capability identifiers
- `description`: Human-readable description

## Permission Hierarchy

Permission scopes follow a hierarchy:

1. **read-only** (level 1): Can only read data
2. **read-write** (level 2): Can read and write data
3. **execute** (level 3): Can execute operations
4. **admin** (level 4): Full administrative access

Higher levels include all permissions from lower levels.

## Security Considerations

### HTTP Client
- Always use HTTPS in production
- Store tokens in `.env.mcp` or environment variables
- Implement rate limiting on the server side
- Validate all responses before use

### Process Client
- Validate command and arguments before execution
- Use sandboxed execution environments
- Set appropriate timeouts to prevent hanging
- Monitor process health and resource usage
- Implement proper cleanup on shutdown

### Embedded Loader
- Validate server paths are within repository
- Enforce permission scopes strictly
- Use sandboxing for untrusted code
- Audit manifest changes
- Implement security scanning for embedded servers

## Error Handling

All clients implement comprehensive error handling:

```python
from mcp_clients import HttpMCPClient

client = HttpMCPClient("https://example.com/mcp")

try:
    result = await client.call_tool("example", {})
except httpx.HTTPError as e:
    # Handle network errors
    print(f"Network error: {e}")
except ValueError as e:
    # Handle response errors
    print(f"Invalid response: {e}")
except Exception as e:
    # Handle unexpected errors
    print(f"Unexpected error: {e}")
finally:
    client.close()
```

## Testing

Comprehensive test suites are provided in `tests/unit/mcp_clients/`:

- `test_http_mcp_client.py`: HTTP client tests
- `test_process_mcp_client.py`: Process client tests
- `test_embedded_mcp_loader.py`: Embedded loader tests
- `test_mcp_router.py`: Router tests

Run tests with:
```bash
pytest tests/unit/mcp_clients/ -v
```

## Future Enhancements

- Connection pooling for HTTP clients
- Advanced retry strategies (circuit breaker pattern)
- Metrics and telemetry integration
- Caching layer for tool discovery
- Dynamic server registration
- Load balancing across multiple servers
