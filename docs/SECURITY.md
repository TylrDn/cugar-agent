
# 🔐 Security & Secrets Policy

This document defines the current security model, secrets handling practices, and production hardening expectations for the CUGAR agent framework. It reflects **implemented behavior**; aspirational items are labeled explicitly.

---

## 🚧 Key Principles

- **No Secrets in Logs**: Secrets must never be printed, logged, or returned in structured outputs. The controller/executor emit audit logs without automatic redaction, so keep sensitive data out of `goal`, `metadata`, and tool outputs.
- **Policy-Driven Validation**: The only built-in enforcement layer is `PolicyEnforcer` (`src/cuga/agents/policy.py`), which validates metadata and tool input against YAML schemas in `configurations/policies`. If no policy exists, execution proceeds without schema checks.
- **Profile Isolation**: Tool access is sandboxed by profile in `ToolRegistry`, but there is **no OS-level sandbox**.
- **Immutable Inputs (guideline)**: Secrets or tokens passed to tools should be treated as read-only by handlers; this is a best practice, not enforced by code.

---

## 🔑 Secrets Management

There is **no centralized secrets loader** in the agent core. Contributors must:

- Store secrets outside the codebase (e.g., `.env` or runtime environment variables) and avoid committing them.
- Inject secrets directly into tool configs or metadata only when necessary and never log them.
- Validate that required secrets are non-empty before use inside handlers or service wrappers.

---

## ✅ Validation Rules

- Use `PolicyEnforcer` schemas to block missing metadata or malformed inputs before tool execution. Update `configurations/policies/*.yaml` when adding new tools.
- Perform explicit checks for required secrets inside tool handlers; the executor will not do this for you.
- Keep logs and audit traces free of tokens, API keys, and passwords. Redact manually before emitting to `cuga.agents.audit`.

---

## 🧼 Secret Sanitization in Logs

- There are **no built-in redaction helpers** in `controller.py` or `executor.py`. Tool authors must mask or drop sensitive data before logging.
- Keep audit payloads minimal and avoid including raw credentials in `PlanStep.input` or handler outputs.

---

## 🔒 Production Guardrails

The core agent **does not change behavior based on environment variables**. To harden deployments:

- Configure logging to exclude debug/audit output that might include sensitive input.
- Use restrictive policies in `configurations/policies` to disallow unknown tools and enforce schemas.
- Avoid dynamic code execution in tool handlers; this repository does not include a sandbox.
- Add external startup checks for required secrets in your deployment scripts.

---

## 🧪 Security in CI

### Pre-commit Hooks:

If you add new tooling, consider enabling secret scanners such as `detect-secrets` locally. No hook is enforced in this repository today.

### GitHub Actions:

CI pipelines should reject committed `.env` files or secrets; enforcement is handled by downstream workflows, not the agent code.

---

## 📘 Related Docs

- `AGENTS.md` – contributor guardrails
- `TOOLS.md` – how tools consume secrets safely
- `REGISTRY_MERGE.md` – sanitization of fragments with embedded tokens

---

🔁 Return to [Agents.md](../AGENTS.md)
