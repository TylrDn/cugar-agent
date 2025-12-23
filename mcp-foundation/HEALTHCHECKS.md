# MCP & Langflow Healthchecks

Use these checks to verify registry composition and Langflow connectivity.

## Validate merged YAML

```bash
set -euo pipefail
uv run python ./mcp-foundation/scripts/merge_registry.py --profile demo_power --dry-run | head
```

## Check Langflow reachability (DEV)

```bash
set -euo pipefail
curl "$LF_SERVER/api/v1/mcp/streamable"
```

## Confirm CUGA loads MCP servers

```bash
set -euo pipefail
export MCP_SERVERS_FILE=./build/mcp_servers.demo_power.yaml
cuga start demo
```
