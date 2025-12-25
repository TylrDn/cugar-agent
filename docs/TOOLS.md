# 🧰 Tool Interfaces & Execution Model

This document outlines the structure, lifecycle, and execution flow of tools in the CUGAR Agent system **as implemented in `src/cuga/agents`**. It documents what exists today; future-facing ideas must be marked as such.

---

## 🧩 What is a Tool?

A **Tool** is a Python callable registered on a `ToolRegistry` and invoked by the executor for a `PlanStep`.

**Supported today:**
- Local Python callables that accept `(input_dict, *, config, context)`

**Metadata stored in the registry:**
- `name` (per-profile unique)
- `handler` (callable invoked by the executor)
- `config` (dict copied before each call)
- `cost` and `latency` (used by the planner to rank tools)
- `description` (optional; not used by the planner)

When changing tool behavior, edit the handler implementation (e.g., under `src/` or `mcp-*`), update any related policy files in `configurations/policies`, and add or adjust tests under `tests/` to preserve deterministic behavior.

**Not enforced today:**
- Input/output schemas, tags, or return type contracts. Any such validation must be performed manually or via `PolicyEnforcer` schemas.

---

## 📦 Tool Lifecycle

```
Registry.register() → Planner builds PlanStep → Executor resolves handler → Execution → Result
```

1. **Registered** in code on `ToolRegistry` for a specific profile
2. **Sandboxed** to that profile with `ToolRegistry.sandbox(profile)` before use
3. **Selected** by the planner based on cost/latency metadata
4. **Executed** via the executor, which forwards `PlanStep.input` to the handler
5. **Returns** whatever the handler returns; failures propagate as short-circuit results

---

## 🧱 Registering a Tool in Code

```python
from cuga.agents.registry import ToolRegistry

def search_web_handler(input: dict, *, config: dict, context):
    query = input.get("query")
    return {"results": [f"You searched for {query}"]}

registry = ToolRegistry()
registry.register(
    "demo_power",
    "search_web",
    handler=search_web_handler,
    config={"engine": "stub"},
    cost=0.5,
    latency=0.5,
    description="Search web demo",
)
```

---

## 🧠 Tool Interface (Python)

The executor calls handlers with the following signature:

```python
def handler(step_input: dict[str, Any], *, config: dict[str, Any], context: ExecutionContext) -> Any:
    ...
```

**Expectations (not enforced by the executor):**
- Fail loudly if required inputs are missing.
- Avoid side effects or shared mutable state across profiles.
- Return deterministic objects (e.g., dicts) so downstream consumers can rely on shape.

---

## 🧰 Tool Execution Flow

```
Agent Goal
   ↓
Planner builds PlanStep → PlanStep(tool="search_web", input={"goal": "open ai", ...})
   ↓
Executor resolves tool from sandboxed registry (profile scoped)
   ↓
Executor calls: handler(plan_step.input, config=deepcopy(config), context=ExecutionContext(...))
   ↓
Returns handler result or short-circuits on exception
```

---

## 🔐 Security & Scope

- Tools must **not log or return secrets**. The executor does not redact inputs; keep credentials out of `PlanStep.input` and handler outputs.
- Tool access is **profile-scoped** through `ToolRegistry.sandbox`. Cross-profile access is prevented by registry lookups, but no OS-level sandboxing is provided.
- Nested tool invocation is discouraged and not enforced; coordinate via planner/executor rather than calling handlers directly.
- Input/output schema validation is only performed if policies are defined under `configurations/policies` and loaded by `PolicyEnforcer`.

---

## 🧪 Testing a Tool

Each tool should have at least one test under `tests/` that exercises the handler through the executor:

```python
from cuga.agents.executor import Executor, ExecutionContext
from cuga.agents.registry import ToolRegistry
from cuga.agents.planner import PlanStep

def test_search_web_tool():
    registry = ToolRegistry()
    registry.register("demo", "search_web", handler=lambda input, **_: {"results": [input["query"]]})
    executor = Executor()
    context = ExecutionContext(profile="demo", metadata={})
    result = executor.execute_plan(
        [PlanStep(name="step-1", tool="search_web", input={"query": "agent"})],
        registry.sandbox("demo"),
        context,
    )
    assert result.output == {"results": ["agent"]}
```

Use mock APIs or fixed outputs for deterministic behavior. Ensure tests avoid leaking secrets in traces or logs.

---

## 📘 Related Docs

- `AGENT-CORE.md` – Agent pipeline and PlanStep lifecycle
- `REGISTRY_MERGE.md` – How tools are assembled from fragments
- `SECURITY.md` – Secret handling and tool access rules

---

🔁 Return to [Agents.md](../AGENTS.md)

---

## 🛠️ MCP Tool Reference

These MCP tools live in their respective packages under `mcp-*` and `mcp-foundation`. Use the implementation files as the source of truth for accepted parameters and outputs; this section summarizes intent but does **not** add extra guarantees beyond the code.

### scrape_tweets
- **Type:** MCP Tool
- **Purpose:** Scrape tweets from X/Twitter using `snscrape` with profile-scoped execution.

| Input | Type | Description |
| --- | --- | --- |
| `query` | string (required) | Twitter/X search query |
| `limit` | int (optional) | Maximum tweets to return (cap 100) |
| `mode` | string (optional) | Query mode hint (e.g., `recent` or `top`) |

| Output | Type | Description |
| --- | --- | --- |
| `tweets` | list | Collected tweet objects |

Example:

```python
from cuga.mcp.tool_bus import ToolBus

bus = ToolBus()
response = await bus.call("scrape_tweets", method="scrape", params={"query": "open source", "limit": 5})
```

### extract_article
- **Type:** MCP Tool
- **Purpose:** Cleanly extract article content and metadata using `newspaper4k` with sandbox-aware fallbacks.

| Input | Type | Description |
| --- | --- | --- |
| `url` | string (required unless `html`) | Article URL |
| `html` | string (required unless `url`) | Raw HTML to parse |
| `language` | string (optional) | Language hint |
| `timeout_ms` | int (optional) | Download timeout in milliseconds |

| Output | Type | Description |
| --- | --- | --- |
| `article.title` | string | Article title |
| `article.authors` | list | Authors if discovered |
| `article.publish_date` | string/null | ISO publish date |
| `article.text` | string | Extracted body text |
| `article.top_image` | string/null | Top image URL |
| `article.keywords` | list | Extracted keywords (may be empty) |
| `article.summary` | string/null | Summary if available |

Example:

```python
from cuga.mcp.tool_bus import ToolBus

bus = ToolBus()
response = await bus.call("extract_article", method="extract", params={"html": sample_html})
```

### crypto_wallet
- **Type:** MCP Tool
- **Purpose:** Wrapper for crypto mnemonic, validation, derivation, and signing workflows.

| Input | Type | Description |
| --- | --- | --- |
| `operation` | string (required) | One of `generate_mnemonic`, `validate_mnemonic`, `derive_address`, `sign_message` |
| `params` | object | Operation-specific arguments |

| Output | Type | Description |
| --- | --- | --- |
| `data` | object | Operation result payload |

Example:

```python
from cuga.mcp.tool_bus import ToolBus

bus = ToolBus()
resp = await bus.call("crypto_wallet", method="operate", params={"operation": "generate_mnemonic", "params": {"word_count": 12}})
```

### moon_agents
- **Type:** MCP Tool
- **Purpose:** Provide reusable Moon agent patterns and lightweight plan generation.

| Input | Type | Description |
| --- | --- | --- |
| `action` | string (required) | `list_patterns` or `generate_plan` |
| `params` | object | Action-specific parameters |

| Output | Type | Description |
| --- | --- | --- |
| `result` | object | Patterns list or generated plan |

Example:

```python
from cuga.mcp.tool_bus import ToolBus

bus = ToolBus()
resp = await bus.call("moon_agents", method="run", params={"action": "list_patterns"})
```

### vault_tools
- **Type:** MCP Tool
- **Purpose:** Curated utilities inspired by `awesome-mcp-servers`, including JSON querying, profile-scoped KV storage, and clock access.

| Input | Type | Description |
| --- | --- | --- |
| `tool` | string (required) | `json_query`, `kv_store`, or `time_now` |
| `params` | object | Tool-specific parameters |

| Output | Type | Description |
| --- | --- | --- |
| `result` | object | Tool-specific output |

Example:

```python
from cuga.mcp.tool_bus import ToolBus

bus = ToolBus()
resp = await bus.call(
    "vault_tools",
    method="execute",
    params={"tool": "json_query", "params": {"data": {"items": [1, 2]}, "expression": "items[0]"}},
)
```
