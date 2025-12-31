.PHONY: profile-demo_power env-dev test docs check-docs lint typecheck format coverage

profile-demo_power:
	uv run python ./mcp-foundation/scripts/merge_registry.py --profile demo_power

env-dev:
	@MCP_SERVERS_FILE=./build/mcp_servers.demo_power.yaml; \
		echo "export MCP_SERVERS_FILE=$$MCP_SERVERS_FILE"; \
		printf "MCP_SERVERS_FILE=$$MCP_SERVERS_FILE\n" > .env.mcp; \
		echo "Wrote .env.mcp (source with: set -a; source .env.mcp; set +a)"

test:
	uv run pytest -q

coverage:
	uv run pytest --cov=cuga --cov-report=term-missing

lint:
	uv run ruff check .
	uv run black --check .
	uv run isort --check-only .

format:
	uv run black .
	uv run isort .

typecheck:
	uv run mypy src

mcp-mocks:
	uv run python -m tests.mcp.mock_server

docs:
	python3 build/gen_tiers_table.py

check-docs:
	python3 build/gen_tiers_table.py
	git diff --exit-code docs/mcp/tiers.md


# MCP-specific targets
test-mcp:
	@echo "Running MCP-specific tests..."
	PYTHONPATH=src uv run pytest tests/test_registry.py tests/test_mcp_toolbox.py tests/test_executor_mcp.py tests/test_langflow_mcp_component.py tests/test_langflow_roundtrip.py tests/test_mcp_determinism.py -v --override-ini="addopts="

mcp-server:
	@echo "Starting MCP server with tier 1 tools..."
	@echo "Registry: docs/mcp/registry.yaml"
	@echo "Tools available: mcp.github, mcp.fs, mcp.git, etc."

demo-mcp-github:
	@echo "Running MCP GitHub integration demo..."
	@echo "Flow definition: examples/langflow/mcp_github_flow.json"
	PYTHONPATH=src uv run python -c "from cuga.langflow_components.mcp_client import MCPClientComponent; client = MCPClientComponent(); result = client(allowed_tiers='1', tool_ids='mcp.github,mcp.fs', enable_audit=False); print('Loaded tools:', [t['id'] for t in result['tools']]); print('Tool count:', result['tool_count'])"
