# Observability & Budgets

Exact env keys only; set in `.env`, `ops/env/orchestrator.env`, `ops/env/observability.env`, or compose anchors. Prefer secrets managers for production.

## Sampling
- `AGENT_TRACE_SAMPLE_RATE` (0.0–1.0, highest priority)
- fallback `OTEL_TRACES_SAMPLER`
- fallback `OTEL_TRACES_SAMPLER_ARG`

## Latency Budgets
- `AGENT_TRACE_MAX_LATENCY_MS`
- `AGENT_TOOL_MAX_LATENCY_MS` (per-tool)

## Cost / Budget Controls
- `AGENT_RUN_BUDGET_USD`
- `AGENT_DAILY_BUDGET_USD`
- `AGENT_BUDGET_ENFORCE` (`warn|block`)

## Providers
- LangFuse: `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`
- LangSmith: `LANGCHAIN_TRACING_V2`, `LANGCHAIN_ENDPOINT`, `LANGCHAIN_API_KEY`, `LANGCHAIN_PROJECT`
- OTEL: `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_EXPORTER_OTLP_HEADERS`

## Operator Tuning
- Start with `AGENT_TRACE_SAMPLE_RATE=0.1` and raise on incidents.
- Use `AGENT_BUDGET_ENFORCE=warn` in staging; `block` in production when caps are known.
- Keep latency caps close to SLOs; propagate the same values into orchestrator env files and compose overrides.
