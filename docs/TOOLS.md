# 🧰 Tool Interfaces & Execution Model

This document outlines the structure, lifecycle, and execution flow of tools in the CUGAR Agent system.

---

## 🧩 What is a Tool?

A **Tool** is a modular, callable capability used by the agent to accomplish steps in a plan.  
Tools can be:

- Local Python functions
- Wrapped APIs (e.g., via OpenAPI or MCP)
- Scripted CLI interfaces
- Language model endpoints

Each tool must declare:
- Its **name**
- **Input schema**
- **Output schema**
- Optional **metadata** (description, tags, etc.)

---

## 📦 Tool Lifecycle

```
YAML Fragment → Registry → PlanStep → Execution → Result
```

1. **Defined** in profile registry YAML (`configurations/profiles/`)
2. **Loaded** and sandboxed into `ToolRegistry`
3. **Matched** to a PlanStep during planning
4. **Executed** with structured inputs
5. **Returns** structured result or failure

---

## 🧱 Tool YAML Fragment Example

```yaml
tools:
  - name: search_web
    type: local
    module: tools.web.search
    description: Search the web using a local engine
    inputs:
      query: str
    outputs:
      results: List[str]
```

---

## 🧠 Tool Interface (Python)

Each tool should subclass or comply with a base interface like:

```python
class Tool:
    name: str
    inputs: Dict[str, type]
    outputs: Dict[str, type]

    def run(self, **kwargs) -> Dict:
        ...
```

**Key Requirements**:
- Fail loudly if inputs are missing
- Always return a dict matching the output schema
- Avoid side effects or global state

---

## 🧰 Tool Execution Flow

```
Agent Goal
   ↓
Planner builds PlanStep → {"tool": "search_web", "inputs": {"query": "open ai"}}
   ↓
Executor resolves tool from Registry
   ↓
Executor calls: tool.run(**inputs)
   ↓
Returns: {"results": [...]}
```

---

## 🔐 Security & Scope

- Tools must **not access secrets directly** (use config injections or scoped APIs)
- Tools must be **scoped to the profile**
- Tools must NOT call other tools directly (no nesting)

---

## 🧪 Testing a Tool

Each tool should have at least one test under `tests/`:

```python
def test_search_web_tool():
    tool = SearchWebTool()
    result = tool.run(query="agent architecture")
    assert "results" in result
```

Use mock APIs or fixed outputs for deterministic behavior.

---

## 📘 Related Docs

- `AGENT-CORE.md` – Agent pipeline and PlanStep lifecycle
- `REGISTRY_MERGE.md` – How tools are assembled from fragments
- `SECURITY.md` – Secret handling and tool access rules

---

🔁 Return to [Agents.md](../AGENTS.md)
