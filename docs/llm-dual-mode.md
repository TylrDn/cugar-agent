# Dual LLM modes

Provider-agnostic adapter supports local, hosted, and hybrid routes without code changes.

- Config: `src/cuga/settings.toml` `[llm]` with optional `[primary]`, `[fallback]`, `[policy]`; env placeholders `${OPENAI_API_KEY}` expanded using `.env` < `ops/env/orchestrator.env` < live env.
- Modes: Local (`base_url` -> OpenAI-compatible server, no key), Hosted (blank `base_url`, API key in env), Hybrid (primary local + hosted fallback).
- Policy: toggle timeout/context/budget fallback; budgets via `AGENT_RUN_BUDGET_USD`, `AGENT_DAILY_BUDGET_USD`, `AGENT_BUDGET_ENFORCE` (`warn|block`). Local calls cost $0.
- Reliability: `timeout_s`, `max_retries`; tracing hooks carry usage/cost fields. Default transport uses [LiteLLM](https://github.com/BerriAI/litellm) for routing/retries; set `CUGA_LLM_BACKEND=httpx` to force the lightweight built-in client when needed (e.g., offline tests).
- Validation: local server reachable on `11434`, demo UI on `http://localhost:8005`, swapping `base_url` takes effect on reload.
- Ops: `ops/docker-compose.proposed.yaml` adds optional `ollama` service (`local-llm` profile) and mounts `settings.toml` into the app container.

