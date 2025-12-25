# Integration Plan

**Top action (pre-task):** Update and strengthen `AGENTS.md` guardrails (tool allowlist/denylist, escalation ceilings, redaction rules, budget caps) before enabling any Tier 1 defaults.

## Milestones (with acceptance & kill switches)
1) **Tier 1 registry + compose wiring**
   - Acceptance: registry + compose alignment validated; tiers table auto-generated.
   - Kill-switch: disable Tier 1 entries via registry `enabled:false` and stop Tier 1 compose profile.
2) **Sandbox enforcement**
   - Acceptance: sandbox profiles mapped to compose services with read-only defaults and healthchecks.
   - Kill-switch: freeze sandbox profile to `py-slim` and block outbound network.
3) **Observability & budgets**
   - Acceptance: env keys wired in orchestrator and collector; sampling and budget caps documented.
   - Kill-switch: set `AGENT_BUDGET_ENFORCE=block` and `AGENT_TRACE_SAMPLE_RATE=0`.
4) **Tier 2 opt-in modules**
   - Acceptance: Tier 2 services behind compose profiles; registry entries default disabled.
   - Kill-switch: remove Tier 2 profile from compose invocation and keep registry disabled.
5) **Registry-driven hot-swap**
   - Acceptance: swapping an integration only requires registry edit + doc regen; no code changes.
   - Kill-switch: revert to previous registry version and rerun doc generator.
