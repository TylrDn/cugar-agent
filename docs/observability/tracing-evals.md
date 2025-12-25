# Observability, Tracing, and Evaluations

## Tracing Model
- OTEL-compatible spans from **controller → planner → registry merge → sandbox runner → tool invocation → result handling**.
- Correlation IDs generated per request; propagated through Langflow nodes, ALTK lifecycle hooks, and MCP adapters.
- MCP runners attach span attributes: sandbox profile, registry entry, tool URI/version, resource usage, retries, and redaction status.
- Sampling: default head-sampling 20% in dev, 5% in prod with dynamic upsampling on errors; override per profile.
- Redaction: client-side scrubbing of secrets/PII before export; hashed identifiers for users and repo names in traces.

## Metrics and Budgeting
- Latency, success/error rates, sandbox queue depth, and token/compute spend per tool.
- Alerting thresholds: P95 stdio MCP <3s, HTTP MCP <6s; sandbox start <15s; error rate <2% per tool; budget caps for external APIs.
- Health probes for MCP endpoints; circuit breakers trip after consecutive failures with exponential backoff.

## Evaluations and Red-team Signals
- Golden traces stored per scenario (web ingest, VCS read-only, vector query) with diff tooling to detect regression.
- Offline fixtures for MCP responses; CI avoids live network calls.
- Red-team scenarios exercised regularly: prompt injection via web payloads, sandbox escape attempts, secret leakage to logs or tracing sinks, VCS exfiltration via diff abuse.
- Metrics include redaction effectiveness (blocked/flagged events) and sandbox policy violations.

## Export Destinations
- LangSmith and LangFuse supported as opt-in exporters; disable entirely in sensitive environments.
- Local development uses file-based OTEL collector with retention limits; prod deployments ship via secure channel with TLS/mTLS.
