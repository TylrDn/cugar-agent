# Testing Guide

This project uses `uv` for dependency management and `pytest` for execution. Tests are grouped to keep registry checks, e2e tasks, and sandbox features isolated.

## Setup
```bash
uv sync --all-extras --dev
uv run playwright install --with-deps chromium
```

## Fast checks
Run the guardrail verifier and linters before opening a pull request:

```bash
python scripts/verify_guardrails.py
uv run ruff check
uv run ruff format --check
```

## Unit and integration tests
Use the bundled test runner to mirror CI behavior. The script runs linters first, then exercises multiple suites.

```bash
# Registry + variables manager + sandbox + E2B lite + selected e2e flows
bash src/scripts/run_tests.sh

# CI-style unit slice
bash src/scripts/run_tests.sh unit_tests
```

CI runs `pytest --cov=src --cov-report=term-missing --cov-fail-under=80` and the stability harness `python src/scripts/run_stability_tests.py` to guard planner/registry/guardrail regressions.

If you need memory-backed tests, enable the memory dependency group before running them (the helper does this automatically for the memory suites it triggers).

## Tips
- Close stray processes on ports 7860, 8000, 8001, 8888, and 9000 when tests spawn local services.
- Use `PYTEST_ADDOPTS="-k <pattern>"` to narrow scope when debugging.
- When changing registry fragments or guardrails, rerun `python scripts/verify_guardrails.py` to ensure routing markers stay in sync.
