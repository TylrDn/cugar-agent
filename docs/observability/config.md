Config entry points (set in .env or ops/env/{orchestrator.env,observability.env}; compose anchors in /ops/docker-compose.proposed.yaml)

Sampling
- AGENT_TRACE_SAMPLE_RATE (default: 0.1)
- fallback: OTEL_TRACES_SAMPLER=traceidratio, OTEL_TRACES_SAMPLER_ARG=${AGENT_TRACE_SAMPLE_RATE}

Latency budgets
- AGENT_TRACE_MAX_LATENCY_MS (default: 5000)
- per-tool override: AGENT_TOOL_MAX_LATENCY_MS (map or comma list alias=ms)

Cost/budget
- AGENT_RUN_BUDGET_USD (default: 5)
- AGENT_DAILY_BUDGET_USD (default: 20)
- AGENT_BUDGET_ENFORCE (warn|block, default: warn)

Providers
- LangFuse: LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY
- LangSmith: LANGCHAIN_TRACING_V2=on, LANGCHAIN_ENDPOINT, LANGCHAIN_API_KEY, LANGCHAIN_PROJECT
- OTEL exporter: OTEL_EXPORTER_OTLP_ENDPOINT, OTEL_EXPORTER_OTLP_HEADERS

Compose wiring (examples as comments)
- orchestrator service consumes sampling/latency/budget vars
- observability sidecar consumes provider/OTEL vars
- vector-db optional service can emit traces via OTEL vars

Operator tuning (one-liners)
- Adjust sample rate: set AGENT_TRACE_SAMPLE_RATE=0.05 for lighter tracing.
- Tighten latency: set AGENT_TRACE_MAX_LATENCY_MS=2000 and per-tool overrides in env.
- Enforce budget: AGENT_RUN_BUDGET_USD=2 with AGENT_BUDGET_ENFORCE=block to hard-stop high-cost runs.
- Switch providers: set LANGCHAIN_TRACING_V2=on and LANGCHAIN_API_KEY to route to LangSmith; or set LANGFUSE_* to enable LangFuse; leave unset to stay local.
