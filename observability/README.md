# Observability

Tracing and telemetry helpers live in `src/cuga/modular/observability.py`.

- Langfuse support via `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY`.
- OpenInference/Traceloop toggles via `OPENINFERENCE_ENABLED`/`TRACELOOP_API_KEY`.
- Sampling and redaction hooks default to safe settings; adjust in `configs/observability.yaml`.
