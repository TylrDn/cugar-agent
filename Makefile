.PHONY: profile-demo_power env-dev test

profile-demo_power:
	uv run python ./mcp-foundation/scripts/merge_registry.py --profile demo_power

env-dev:
	@MCP_SERVERS_FILE=./build/mcp_servers.demo_power.yaml; \
		echo "export MCP_SERVERS_FILE=$$MCP_SERVERS_FILE"; \
		printf "MCP_SERVERS_FILE=$$MCP_SERVERS_FILE\n" > .env.mcp; \
		echo "Wrote .env.mcp (source with: set -a; source .env.mcp; set +a)"

test:
	uv run pytest -q
