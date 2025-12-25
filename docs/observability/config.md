# Observability and Budget Controls

Set env keys in `.env`, `ops/env/orchestrator.env`, `ops/env/observability.env`, or compose anchors in `ops/docker-compose.proposed.yaml`.

Sampling
- AGENT_TRACE_SAMPLE_RATE (preferred)
- fallback: OTEL_TRACES_SAMPLER, OTEL_TRACES_SAMPLER_ARG

Latency budgets
- AGENT_TRACE_MAX_LATENCY_MS
- AGENT_TOOL_MAX_LATENCY_MS (comma/JSON map per tool)

Cost/budget
- AGENT_RUN_BUDGET_USD
- AGENT_DAILY_BUDGET_USD
- AGENT_BUDGET_ENFORCE (warn|block)

Providers
- LangFuse: LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY
- LangSmith: LANGCHAIN_TRACING_V2, LANGCHAIN_ENDPOINT, LANGCHAIN_API_KEY, LANGCHAIN_PROJECT
- OTEL: OTEL_EXPORTER_OTLP_ENDPOINT, OTEL_EXPORTER_OTLP_HEADERS

Operator tuning
- Lower sample rate to reduce load: AGENT_TRACE_SAMPLE_RATE=0.05 (or OTEL_TRACES_SAMPLER=traceidratio + OTEL_TRACES_SAMPLER_ARG=0.05).
- Tighter latency: AGENT_TRACE_MAX_LATENCY_MS=2000 plus AGENT_TOOL_MAX_LATENCY_MS=search=1500,tool=3000.
- Budgets: AGENT_RUN_BUDGET_USD=5, AGENT_DAILY_BUDGET_USD=20, AGENT_BUDGET_ENFORCE=warn or block.
- Provider routing: set LangSmith or LangFuse vars above; leave unset to keep traces local/export via OTEL only.
