# Threat Model (STRIDE-lite)

## Scope and Assets
- Assets: credentials, registry fragments, traces, source data, vector indexes, backups.
- Boundaries: profile-scoped sandboxes (E2B/Docker), registry merge pipeline, observability exports, VCS ingest flows.

## STRIDE Considerations
- **Spoofing**: token scopes per MCP; optional mTLS between orchestrator and MCP servers; signed registry entries to prevent forgery.
- **Tampering**: read-only defaults for VCS operations; checksums for artefacts; append-only audit logs with integrity checks; backups verified via hash.
- **Repudiation**: correlation IDs per request; monotonic timestamps; audit trails streamed to local storage with optional mirrored traces.
- **Information Disclosure**: sandbox filesystem isolation; outbound network allowlists; secret/PII redaction before logging or export; per-profile namespaces for vector DB and memory.
- **Denial of Service**: rate limits per MCP server; sandbox CPU/memory/time caps; circuit breakers for failing endpoints; backlog limits on schedulers.
- **Elevation of Privilege**: containers run as non-root with seccomp/default capability drops; no host mounts; validate tool commands against allowlists.

## Kill-switches and Response
- Disable MCP entries in registry to quarantine compromised tools; revoke tokens immediately.
- Pause sandbox pools on suspicious activity; force-read-only mode for VCS and filesystem MCPs during incident response.
- Maintain emergency blocklists for domains, repos, and registry variants; document post-incident follow-ups.
