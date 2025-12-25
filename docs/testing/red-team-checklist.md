# Red-Team Checklist and Testing Strategy

## Security Scenarios
- **Prompt injection**: craft hostile HTML/JS and markdown via Browser MCP; verify sanitization and allowlists in Langflow nodes.
- **Path traversal / SSRF**: attempt `file://`, `..`, and internal host fetches; confirm Browser MCP blocks and logs refusals.
- **Sandbox escape**: run syscalls/capability probes inside E2B/Docker profiles; ensure seccomp/cgroup enforcement and audit entries.
- **Secret leakage**: inspect traces/logs for tokens/PII; ensure redaction filters trigger before export to LangSmith/LangFuse/OTEL.
- **VCS exfiltration**: simulate diff-based leak attempts; verify read-only scopes and secret scanners on outputs.

## Regression Harness
- **Unit**: mocked MCP clients for registry merge, sandbox selection, timeout/retry paths; fixture-based outputs for snscrape/newspaper4k.
- **Integration**: docker-compose profile with MCP mocks; golden traces captured per scenario and compared with diff tooling.
- **Langflow golden flows**: record controller/planner/tool traces for representative graphs; compare span trees and payload redactions across runs.
- **Offline-first**: CI uses cached fixtures; no live network calls; sandbox resource caps enforced in tests.

## Execution Notes
- Each scenario tagged by profile and capability for repeatability.
- Document any guardrail regression in `CHANGELOG.md` and update fixtures when schemas change.
- Provide kill-switch steps with every test case (disable registry entry, block domain, or force read-only mode).
