# CUGA Agent Architecture

CUGA is a controller-led, hierarchical multi-agent system that combines planners, executors, and MCP-powered tool packs under a single registry. Use this page as the opinionated source of truth for how the pieces fit together and where to tune behavior.

## 1) High-level flow

```
┌──────────────┐    selects mode     ┌──────────────────────────┐    produces plans    ┌────────────────────┐
│  Settings &  │ ─────────────────▶ │    Plan Controller       │ ───────────────────▶ │   Planners &        │
│  Registry    │   (cuga_mode +     │ (task intake + routing,  │    (task/walkthrough │   Shortlister       │
│ (settings +  │    task mode)      │  state + trace_id owner) │      design)         │   (quality filter)  │
└─────┬────────┘                    └──────────┬───────────────┘                     └──────┬──────────────┘
      │                                      sub-tasks | tools                                │ filtered plans
      │                                                ▼                                        │
      │                              ┌─────────────────────────┐                    ┌───────────▼───────────┐
      │                              │   Executors & Tools     │ ◀── tool calls ─── │  MCP / Registry Tool  │
      │                              │ (API/MCP runners, code  │ ── tool results ▶  │ Surface (registry.yaml│
      │                              │ agent, browser actions) │                    │ + mcp-* bundles)      │
      │                              └───────────┬────────────┘                    └───────────┬───────────┘
      │                                          │                                           │
      │                                   reflection / retries                              │
      │                                          │                                           │
      ▼                                          ▼                                           ▼
┌───────────────────┐                   ┌──────────────────┐                        ┌──────────────────────┐
│   Memory / RAG    │ ◀─ context ───── │ Reflection &     │ ◀─ steps/outputs ───── │  Answer synthesis    │
│ (optional)        │                  │ policy guardrails│                         │ (final response)     │
└───────────────────┘                   └──────────────────┘                        └──────────────────────┘
```

### Narrative
- **Plan Controller** (`src/cuga/agents/controller.py`) ingests the user goal, reads reasoning + task mode from `src/cuga/settings.toml`, and owns the `trace_id`.
- **Planners** (`src/cuga/agents/planner.py` and `src/cuga/agents/planners/*`) break the goal into steps. Task decomposition and the shortlister trim bad/duplicate plans before execution.
- **Executors** (`src/cuga/agents/executor.py` and `src/cuga/agents/executors/*`) run API/MCP tools and route complex logic to the code agent. They always sandbox per profile.
- **Tools/Registry**: MCP and registry-backed tools are declared in `registry.yaml` plus `src/cuga/backend/tools_env/registry/config/*.yaml` and surfaced to planners/executors.
- **Reflection + Answer**: Reflection agents verify intermediate results and trigger retries; the answer agent synthesizes the final reply for the caller.

## 2) Instruction sets (how each role behaves)
Agent behavior is driven by instruction markdown files and selected via `src/cuga/configurations/instructions/instructions.toml`:

```
[instructions]
instruction_set = "default"  # set to another folder name to customize
```

Default set lives in `src/cuga/configurations/instructions/default/`:
- `plan_controller.md` – orchestrator rules (mode selection, stopping criteria, policy hints).
- `task_decomposition.md` – how to split goals into structured sub-tasks.
- `api_planner.md` and `api_code_planner.md` – design multi-step API/MCP call sequences (with/without inline code glue).
- `shortlister.md` – filters/ ranks candidate plans to reduce duplicates and risk.
- `code_agent.md` – how code is generated/executed when planners delegate to code.
- `reflection.md` – validation, retries, and repair guidance.
- `answer.md` – synthesizes final user-facing responses.

**Customize** by copying `default/` to a new folder (e.g., `my_org/`), editing the markdown, and updating `instruction_set` to point at your folder.

## 3) Reasoning + task modes
Reasoning modes trade speed for depth. They live in `src/cuga/configurations/modes/`:
- `fast.toml` – aggressive heuristics, minimal planning.
- `balanced.toml` (default) – cost vs. reliability trade-off.
- `accurate.toml` – deeper planning and more reflection.
- `custom.toml` – bring your own settings (clone and edit).
- `save_reuse_fast.toml` – fast mode with save/reuse tweaks.

Select the reasoning mode in `src/cuga/settings.toml`:

```
[features]
cuga_mode = "balanced"  # fast | balanced | accurate | custom | save_reuse_fast
```

Task modes define what kind of work CUGA performs and where planners can act. Configure them in `src/cuga/settings.toml`:

```
[advanced_features]
mode = "api"        # api | web | hybrid

[demo_mode]
start_url = "https://..."  # starting URL for web/hybrid demos
```

- `api` – API/tools only.
- `web` – browser-centric tasks (via extension) starting at `demo_mode.start_url`.
- `hybrid` – combines API + browser execution.

## 4) Tools, MCP bundles, and registry
- MCP/domain packs live under the `mcp-*` directories (e.g., `mcp-foundation`, `mcp-plumbing`, `mcp-music-agent`, `mcp-trading-agent`, `mcp-wordpress-agent`).
- Root-level `registry.yaml` lists which MCP servers/services are active per profile or environment.
- MCP server details (endpoints/auth/options) live in `src/cuga/backend/tools_env/registry/config/*.yaml`.

Runtime assembly:
1. CUGA loads `registry.yaml` and merges any profile fragments (see `docs/REGISTRY_MERGE.md`).
2. MCP server definitions are validated and exposed as tools.
3. Planners (especially API planners) see these tools in their available action set.
4. Executors call MCP tools and feed results back to the controller with structured traces.

## 5) Add a new domain agent pack (checklist)
1. **Create the MCP server**: add a new `mcp-<domain>/` folder with the server or adapter logic.
2. **Register it**: add the server to `registry.yaml` (and any per-profile fragments) and, if needed, a config entry under `src/cuga/backend/tools_env/registry/config/` for endpoints/auth.
3. **Nudge planners**: optionally clone `src/cuga/configurations/instructions/default/` to a new set and tune `plan_controller.md` / `api_planner.md` to favor the new domain tools.
4. **Test + docs**: run the relevant planners/executors against the new tools and record the addition in your change notes.

## 6) Policy, HITL, and safety controls
Policy and human-in-the-loop controls are configured in `src/cuga/settings.toml`:

```toml
[advanced_features]
api_planner_hitl = true  # pauses API plans for human approval before execution
```

Typical flow: the planner proposes a multi-step plan, a reviewer approves or edits it, and executors only run the approved version. Tighten `plan_controller.md` / `api_planner.md` in your instruction set to enforce allowed services, PII handling, or change-management steps.

## 7) Memory (optional)
Long-term memory is opt-in. To enable:
- Install memory extras (see `README` / `docs`).
- Set `enable_memory = true` in your active settings TOML.
- Start CUGA in a memory-aware mode (for example, `cuga start memory`).

The controller and planners then reuse previous trajectories, recall successful tool calls, and maintain cross-task context for long-running workflows.

## 8) Extending this repo (agent capability checklist)
When adding a new agent role or capability:
1. **Pick the role**: planner, executor, reflection/helper, or UI-side assistant.
2. **Wire tools**: add an MCP server or OpenAPI spec, then register it in `registry.yaml` (and `src/cuga/backend/tools_env/registry/config/` if it needs connection details).
3. **Create/update instructions**: edit or add markdown under your instruction set to define what the agent does, when to invoke it, and any safety constraints.
4. **Tune modes/policies**: choose reasoning + task modes, and enable HITL or sandboxed code execution if needed.
5. **Document**: update this file with any new roles or domains so contributors see the full multi-agent picture at a glance.

## 9) Deep-dive references
- **MCP integration**: `docs/MCP_INTEGRATION.md`.
- **Registry merging**: `docs/REGISTRY_MERGE.md`.
- **Agent guardrails**: root `AGENTS.md`.
- **Existing architecture summary**: `ARCHITECTURE.md` and `docs/architecture/` for broader platform views.

## Vector memory tunables
- Default connector: `cuga.memory.vector.VectorMemory` with async `batch_upsert` and `similarity_search` primitives.
- Retention: configure `ttl_seconds` for time-based eviction and `max_items` for bounded windows; eviction runs on every write/read.
- Batching: callers should group writes by interaction to preserve ordering and reduce contention; tests cover stress retention paths.
