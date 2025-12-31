.PHONY: profile-demo_power env-dev test docs check-docs lint typecheck format coverage test-mcp demo-mcp-github mcp-server

profile-demo_power:
	uv run python ./mcp-foundation/scripts/merge_registry.py --profile demo_power

env-dev:
	@MCP_SERVERS_FILE=./build/mcp_servers.demo_power.yaml; \
		echo "export MCP_SERVERS_FILE=$$MCP_SERVERS_FILE"; \
		printf "MCP_SERVERS_FILE=$$MCP_SERVERS_FILE\n" > .env.mcp; \
		echo "Wrote .env.mcp (source with: set -a; source .env.mcp; set +a)"

test:
        uv run pytest -q

test-mcp:
	@echo "Running MCP integration tests..."
	PYTHONPATH=src python3 -m pytest tests/test_registry.py tests/test_mcp_toolbox.py tests/test_executor_mcp.py tests/test_mcp_determinism.py tests/test_langflow_mcp_component.py tests/test_langflow_roundtrip.py -v --no-cov

demo-mcp-github:
	@echo "=== MCP GitHub Demo ==="
	@echo "Loading MCP tools from registry..."
	@PYTHONPATH=src python3 -c "from cuga.tools.mcp_toolbox import create_mcp_toolbox; \
		toolbox = create_mcp_toolbox(allowed_tiers=[1], deny_by_default=True); \
		print(f'Loaded {len(toolbox._tools)} MCP tools:'); \
		print('\\n'.join(f'  - {tid}' for tid in toolbox.list_tool_ids())); \
		print('\\nExecuting mcp.github demo...'); \
		result = toolbox.execute_tool('mcp.github', {'action': 'demo'}, {'trace_id': 'demo123'}); \
		print(f'Result: {result}')"

mcp-server:
	@echo "Starting local MCP server for development..."
	@echo "This would start MCP servers defined in docs/mcp/registry.yaml"
	@echo "Not implemented yet - placeholder for future development"

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
