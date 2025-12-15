#!/usr/bin/env bash

# Display usage information if help is requested
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo "Usage: $0 [OPTION]"
    echo ""
    echo "Test runner script with multiple options:"
    echo "  (no args)    Run registry tests only"
    echo "  e2e_tests    Run all tests (registry + e2e system tests)"
    echo "  simple       Run simple tests (registry + e2e without save_reuse tests)"
    echo "  --help, -h   Show this help message"
    echo ""
    exit 0
fi

echo "Starting unit tests with uv..."

echo "Running ruff check..."
if ! uv run ruff check; then
    echo "❌ Ruff check failed!"
    exit 1
fi

echo "Running ruff format..."
if ! uv run ruff format --check; then
    echo "❌ Ruff format check failed!"
    exit 1
fi

# Initialize exit code tracker
TEST_EXIT_CODE=0

# Helper function to run pytest and track failures
run_pytest() {
    uv run pytest "$@" -v
    local ec=$?
    echo "pytest $* exited with code $ec"
    TEST_EXIT_CODE=$((TEST_EXIT_CODE | $?))
}

# Helper function to run pytest with memory dependencies installed
run_pytest_with_memory() {
    # Sync memory dependency groups before running tests
    uv sync --group memory
    uv run pytest "$@" -v
    local ec=$?
    echo "pytest (with memory) $* exited with code $ec"
    TEST_EXIT_CODE=$((TEST_EXIT_CODE | $?))
}

# Check for test type flag
if [ "$1" = "full_tests" ]; then
    echo "Running full tests (registry + e2e system tests + variables manager tests)..."
    rm -f ./src/cuga/backend/tools_env/registry/mcp_servers/saved_flows.py
    echo "Running all tests (registry + e2e system tests)..."
    # run_pytest_with_memory ./src/system_tests/unit/test_memory.py ./src/system_tests/e2e/test_memory_integration.py
elif [ "$1" = "unit_tests" ]; then
    echo "Running unit tests (registry + variables manager + local sandbox tests + E2B lite tests)..."
    run_pytest ./src/cuga/backend/tools_env/registry/tests/
    run_pytest ./src/cuga/backend/cuga_graph/nodes/api/variables_manager/tests/
    run_pytest ./src/system_tests/e2e/test_runtime_tools.py
    run_pytest ./src/cuga/backend/tools_env/code_sandbox/tests/
    run_pytest ./src/cuga/backend/cuga_graph/nodes/cuga_lite/tests/
    run_pytest ./src/system_tests/unit/test_sandbox_async.py
    run_pytest ./src/cuga/backend/cuga_graph/nodes/api/code_agent/test_extract_codeblocks.py
    run_pytest ./src/system_tests/unit/test_variable_creation_order.py
    # run_pytest_with_memory ./src/system_tests/unit/test_memory.py ./src/system_tests/unit/test_cli.py
else
    echo "Running default tests (registry + variables manager + local sandbox + E2B lite + e2e without save_reuse and without sandbox docker)..."
    run_pytest ./src/cuga/backend/tools_env/registry/tests/
    run_pytest ./src/cuga/backend/cuga_graph/nodes/api/variables_manager/tests/
    run_pytest ./src/cuga/backend/tools_env/code_sandbox/tests/
    run_pytest ./src/cuga/backend/cuga_graph/nodes/cuga_lite/tests/
    run_pytest ./src/system_tests/e2e/balanced_test.py ./src/system_tests/e2e/fast_test.py ./src/system_tests/e2e/test_runtime_tools.py
    run_pytest ./src/cuga/backend/cuga_graph/nodes/api/code_agent/test_extract_codeblocks.py
    run_pytest ./src/system_tests/unit/test_variable_creation_order.py
    # run_pytest_with_memory ./src/system_tests/unit/test_memory.py ./src/system_tests/unit/test_cli.py
    run_pytest_with_memory ./src/system_tests/e2e/test_memory_integration.py
    run_pytest_with_memory ./src/system_tests/e2e/balanced_test_memory.py

fi

echo "Tests completed with exit code: $TEST_EXIT_CODE"
exit $TEST_EXIT_CODE
