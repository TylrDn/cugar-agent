# MCP Tooling Governance

- **Naming**: Tools must follow the `<domain>__<action>` pattern (e.g., `trading__quote_fetch`).
- **Descriptions**: Use imperative, specific wording and annotate side effects, e.g., "Creates a post on WordPress (side-effect: write)".
- **Scope isolation**: Each subagent keeps its tools in its own registry fragment; profiles only merge intentionally selected fragments.
- **Auth**: Favor header injection via proxies; never embed secrets in YAML. Use environment-variable placeholders only.
- **Safety**: Tag descriptions with `read-only` or `write`; require human approval gates for any write-path tools.
- **Langflow**: Ensure flows expose clear Tool names and descriptions—avoid opaque IDs or UUID-style labels.
- **Rollback**: Provide `dry_run` parameters for write-capable tools whenever possible to enable safe rollbacks.
- **Observability**: Enable MCP progress notifications (when supported) and log tool invocations with inputs redacted.
