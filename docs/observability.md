# Observability Baseline

- Spans emitted via `cuga.observability.InMemoryTracer` with redaction of `secret`, `token`, `password` keys.
- Trace propagation flows planner → coordinator → worker → tool through `trace_id` contextvars and HTTP headers.
- Dashboards use OTEL-compatible fields: `trace_id`, `span`, `tool`, `status`.
- Logs are structured dictionaries; avoid PII and enforce allowlisted env keys.
