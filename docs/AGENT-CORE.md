
# 🧠 Agent Lifecycle & Core Modules

This document breaks down the **internal flow of the CUGAR agent system** as it is implemented today, including each stage of the agent pipeline: Controller → Planner → Executor → Registry.

---

## 📦 Overview

The CUGAR agent is built as a **modular and composable system**. It is composed of 4 tightly scoped components, each with a specific role and contract:

```
User → Controller → Planner → Executor → Tool Registry
```

Each component lives in its own module under `src/cuga/agents/` and must respect the universal guardrails defined in [`AGENTS.md`](../AGENTS.md).
Contributors modifying these components should update the corresponding file in `src/cuga/agents/`, refresh any affected docs in this directory, and add/adjust coverage under `tests/`.

---

## 🧭 1. Controller – Orchestrator

**File**: `controller.py`
**Class**: `Controller`
**Responsibilities**:
- Receives agent `goal`, `profile`, and optional `metadata`
- Validates execution metadata through `PolicyEnforcer`
- Creates a **profile-sandboxed** view of the registry via `ToolRegistry.sandbox`
- Delegates planning to the Planner and execution to the Executor
- Emits an audit event for the controller run and appends planner/executor traces

**Key Method**:
```python
def run(goal: str, profile: str, *, metadata: dict[str, Any] | None = None,
        preferences: PlanningPreferences | None = None) -> ExecutionResult:
    ...
```

**Notes**:
- The controller only orchestrates already-registered tools; **it does not load YAML fragments or external registries.** Callers must construct and populate `ToolRegistry` beforehand.
- Audit logging currently writes to the `cuga.agents.audit` logger without automatic redaction; avoid sending secrets in `goal` or `metadata`.

---

## 🧠 2. Planner – Task Decomposer

**File**: `planner.py`
**Class**: `Planner`
**Responsibilities**:
- Converts the user's goal into an **ordered list of `PlanStep` objects**
- Scores tools by `cost` and `latency` metadata stored in the registry and chooses the cheapest subset
- Emits trace messages describing scoring/selection decisions

**Key Output**:
```python
List[PlanStep]
```

**PlanStep** contains:
- `name`: a stable step label
- `tool`: the tool name to execute (must exist in the sandboxed registry)
- `input`: a dict of arguments provided directly to the tool handler

**Current limitations**:
- Planner only considers the **first available profile** in the provided registry sandbox and does not merge or multi-select profiles.
- There is **no validation** that required input fields exist beyond optional policy checks.

---

## 🧰 3. Executor – Step Runner

**File**: `executor.py`  
**Class**: `Executor`
**Responsibilities**:
- Runs each `PlanStep` in sequence
- Validates metadata and step input only through `PolicyEnforcer` (no schema enforcement is baked into the executor)
- Emits audit records per step via the `cuga.agents.audit` logger

**Failure Handling**:
- Exceptions from a tool handler short-circuit execution and return `ExecutionResult` with the failure payload and trace. **Retries, backoff, and fallbacks are not implemented.**

**Output**:
```python
ExecutionResult {
  success: bool,
  logs: List[str],
  outputs: Dict[str, Any]
}
```

**Additional**:
- Results are logged step-by-step
- Trace entries include controller/planner messages and executor audit records

---

## 🧱 4. Registry – Tool Manager

**File**: `registry.py`  
**Class**: `ToolRegistry`
**Responsibilities**:
- Stores tool handlers registered in code (name, handler, config, cost, latency, description)
- Ensures that tools are isolated per profile (sandboxing)
- Merges tool definitions and enforces conflict detection on `name`

**Operations**:
```python
registry = ToolRegistry()
registry.register("demo_power", "search_web", handler=search_handler, cost=0.5, latency=0.5)
sandboxed = registry.sandbox("demo_power")
sandboxed.resolve("demo_power", "search_web")  # → handler/config snapshot
```

**Design Notes**:
- Registry sandboxes are copies of an already-constructed registry; they **do not pull from disk**.
- No persistent global state is allowed; callers must register tools per profile before invoking the controller.
- Conflicting registrations raise `ValueError` immediately during `register` or `merge`.

---

## 🧪 Future Extensions

Current implementation supports:

- ✅ Local Python callables registered directly on `ToolRegistry`
- ✅ Cost/latency-aware planning over the registered tools
- ✅ Policy-aware metadata and input validation via `PolicyEnforcer`

Planned/Not yet implemented (documented for awareness, not as guarantees):

- 🔄 Multi-agent handoffs
- 🔒 Human-in-the-loop approvals
- 🧠 Persistent memory / replay

---

## 🔁 Return to Hub

Return to [Agents.md](../AGENTS.md) for documentation map and onboarding.
