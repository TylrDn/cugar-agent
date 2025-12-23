.PHONY: profile-demo_power env-dev

profile-demo_power:
uv run python ./mcp-foundation/scripts/merge_registry.py --profile demo_power

env-dev:
@echo "Exporting MCP_SERVERS_FILE to profile output"
@export MCP_SERVERS_FILE=./build/mcp_servers.demo_power.yaml && echo "MCP_SERVERS_FILE=$$MCP_SERVERS_FILE"
