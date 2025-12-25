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

---

## 🛠️ MCP Tool Reference

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
