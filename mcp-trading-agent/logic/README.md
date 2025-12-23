# Trading Subagent Logic

## Purpose
Provide domain-specialized tools and prompts for trading workflows while staying isolated from other agents.

## Enrolled Tools
- `trading__quote_fetch` (read-only): Retrieve market quotes for symbols.
- `trading__order_preview` (read-only with dry-run): Simulate orders before execution.
- `trading__order_execute` (write): Place live orders with required human approval.

## Prompt Examples
- "Fetch the latest quotes for AAPL, MSFT, and GOOGL."
- "Preview a market buy for 10 shares of IBM and summarize required approvals."
- "With approval, place a limit buy for 5 shares of NVDA at $800 and provide rollback options."

## Guardrails & HITL Policies
- All write-path tools (e.g., `trading__order_execute`) require explicit human approval and should expose `dry_run` toggles.
- Descriptions must flag `read-only` vs `write` behaviors and declare side effects.
- Sensitive credentials are provided via environment variables; no secrets in YAML.
- Logging should redact customer identifiers and order quantities beyond what is needed for auditing.
