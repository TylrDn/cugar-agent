# Contributing Guide

Thank you for helping make CUGAR Agent a reliable, modular agent stack. Please follow these steps so changes stay aligned with the guardrails defined in `AGENTS.md`.

## Development Workflow
1. **Create a branch** off `main`: `git checkout -b feature/<short-name>`.
2. **Install dev deps**: `uv sync --all-extras --dev`.
3. **Run checks locally**:
   - `make lint` (ruff + black + isort)
   - `make typecheck` (mypy)
   - `make test` (pytest with coverage)
   - `python scripts/verify_guardrails.py`
4. **Update docs**: touch `CHANGELOG.md` under `## vNext` and any relevant guides (README/USAGE/TESTING/SECURITY).
5. **Open a PR** using `.github/PULL_REQUEST_TEMPLATE/feature.md` (or the best-fitting template). Include:
   - What changed and why
   - Testing performed (commands + results)
   - Guardrail and audit implications
6. **Code review**: at least one maintainer approval; resolve comments before merge.

## Style
- Python >=3.10 with full type hints on public functions/classes.
- Prefer descriptive names over abbreviations; avoid `eval` or dynamic imports.
- Keep functions small and composable; extract helpers where needed.
- No secrets in logs or configs; use env vars and `.env.example` patterns.

## Testing
- Place tests in `tests/` mirroring package layout.
- Use `pytest-cov` to keep coverage signals; mark slow/integration tests with markers.
- When adding tools/agents, include success/failure and guardrail-path tests.

## Documentation
- Keep README, USAGE, TESTING, SECURITY, and AGENTS in sync with behavior.
- Add architecture notes for new modules and update diagrams when necessary.

## Reporting Issues
Use `.github/ISSUE_TEMPLATE` forms. Include repro steps, logs, and environment info. Security concerns should go to the process in `SECURITY.md` rather than public issues.
