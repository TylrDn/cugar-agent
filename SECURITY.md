# Security Policy

CUGAR Agent is sandbox-first. Examples and demos are not production hardened; keep secrets and customer data out of the repository and demos.

## Reporting a Vulnerability
- Email: [security@cuga.dev](mailto:security@cuga.dev)
- Include repro steps, impact, affected version/commit, and any mitigations you tested.
- Do not include credentials or PII. If sensitive artifacts are required, request a secure channel first.
- We aim to acknowledge reports within 72 hours and provide a fix or mitigation timeline within 7 business days.

## Supported Versions
- Active development targets `main`.
- Released tags receive fixes on a best-effort basis; note the tag in your report so we can triage impact.

## Safe Handling Guidelines
- Run agents/MCP servers in sandboxed environments with locked-down network egress by default.
- Configure secrets through environment variables or `.env.mcp`, never in code or committed files.
- Use `python scripts/verify_guardrails.py` and CI workflows to validate routing markers, registry hygiene, and audit/trace settings before shipping.
- Enable observability with redaction when using Langfuse/OpenInference; avoid exporting raw prompts containing sensitive data.
