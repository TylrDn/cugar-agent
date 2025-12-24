
# 🧠 Agent Lifecycle & Core Modules

This document breaks down the **internal flow of the CUGAR agent system**, including each stage of the agent pipeline: Controller → Planner → Executor → Registry.

---

## 📦 Overview

The CUGAR agent is built as a **modular and composable system**. It is composed of 4 tightly scoped components, each with a specific role and contract:

```
User → Controller → Planner → Executor → Tool Registry
```

Each component lives in its own module under `src/cuga/agents/`.

---

## 🧭 1. Controller – Orchestrator

**File**: `controller.py`  
**Class**: `AgentController` (or equivalent)  
**Responsibilities**:
- Receives agent `goal` and `profile`
- Loads and sanitizes the `tool registry` (via sandboxing)
- Delegates planning to the Planner
- Delegates execution to the Executor
- Returns structured output to user/caller

**Key Method(s)**:
```python
def run_agent(goal: str, profile: str) -> AgentResult:
    ...
```

**Notes**:
- Controller is the ONLY module allowed to touch both planner and executor directly.

---

## 🧠 2. Planner – Task Decomposer

**File**: `planner.py`  
**Class**: `AgentPlanner`  
**Responsibilities**:
- Converts the user's goal into an **ordered list of PlanStep objects**
- Validates that tools in the registry match step requirements
- Supports different planning strategies (rule-based, LLM-generated, heuristic)

**Key Output**:
```python
List[PlanStep]
```

**PlanStep** contains:
- `tool`: the tool name to execute
- `inputs`: a dict of required arguments
- `depends_on`: optional dependency chaining

---

## 🧰 3. Executor – Step Runner

**File**: `executor.py`  
**Class**: `AgentExecutor`  
**Responsibilities**:
- Runs each `PlanStep` in sequence
- Validates tool schema before calling
- Handles failures, retries, and fallback behavior

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
- Results may include full tool I/O traces (for Langflow or audit)

---

## 🧱 4. Registry – Tool Manager

**File**: `registry.py`  
**Class**: `ToolRegistry` or equivalent  
**Responsibilities**:
- Loads tools defined by the profile (`YAML` fragments)
- Ensures that tools are isolated per profile (sandboxing)
- Merges tool definitions and enforces conflict detection

**Operations**:
```python
registry = Registry(profile="demo_power")
tools = registry.list()  # → ["search_web", "query_sql"]
registry.resolve("search_web")  # → Tool class instance
```

**Design Notes**:
- Registry is constructed fresh on every agent run.
- No persistent global state allowed.

---

## 🧪 Future Extensions

This core is designed to support:

- ✅ Tool execution via API (OpenAPI/MCP)
- ✅ Local tools (Python modules)
- ✅ Multi-agent handoffs (future)
- 🔒 Human-in-the-loop (planned)
- 🧠 Memory / replay via Embedded Assets

---

## 🔁 Return to Hub

Return to [Agents.md](../AGENTS.md) for documentation map and onboarding.
