
# 🔗 MCP Integration Architecture (v1.0)

This document describes the production-grade integration of **Model Context Protocol (MCP)** tools into the CUGAR Agent framework.

It covers:
- System design
- Configuration model
- Lifecycle management
- Observability and security
- Tool hot-swapping via registry

---

## 🎯 Goals & Scope

### ✅ Goals
- Clear typed interfaces for MCP tools
- Profile + registry-driven tool resolution
- Resilient lifecycle: pooling, retries, timeouts
- Safe defaults: command allow-lists, non-root runners
- Agent-compatible + orchestrator-agnostic (LangChain, AutoGen)

### 🚫 Non-Goals
- Full MCP transport parity
- Centralized control plane
- Built-in default secrets

---

## 🧱 Target Topology

```
agent core
   ↓
tool_bus
   ↓
lifecycle manager
   ↓
runner (transport-specific)
   ├─ subprocess stdio (current)
   ├─ HTTP/SSE (planned)
   └─ container (planned)

↑
registry → config → TOML + env
```

---

## 🧩 Key Components

| Module | Purpose |
|--------|---------|
| `cuga.mcp.interfaces` | Typed request/response models for tools and transports |
| `cuga.mcp.config` | Pydantic models for tools, runners, pools, and security (TOML + env) |
| `cuga.mcp.registry` | Tool registry with semver validation and discovery reload |
| `cuga.mcp.lifecycle` | Starts/stops/query runners, with retries/backoff and breaker logic |
| `cuga.mcp.runners.subprocess_stdio` | Runner for stdio-based tools with log capture |
| `cuga.mcp.adapters.*` | LangChain/AutoGen compatibility |
| `cuga.mcp.telemetry.*` | Logs + metrics (OTEL-ready) |

---

## ⚙️ Configuration Model (TOML)

Example: `mcp_config.toml`

```toml
[mcp]
default_transport = "stdio"
allow_commands = ["python", "uv", "node"]

[mcp.tools.echo]
command = "python"
args = ["-m", "tests.mcp.echo_server"]
version = "0.1.0"
transport = "stdio"
capabilities = ["echo", "health"]

[mcp.pools.default]
max_active = 4
idle_ttl_s = 30
```

### Env Overrides

```bash
CUGA_MCP_CONFIG=/path/to/mcp_config.toml
CUGA_MCP__TOOLS__ECHO__COMMAND=/custom/python
```

---

## 🔁 MCP Tool Lifecycle

1. **Resolve**:
   `tool_bus.call("echo", …)` performs registry lookup + semver validation

2. **Ensure Runner**:
   `lifecycle` ensures a suitable runner (reused or spawned)

3. **Call**:
   Request wrapped in:
   - Timeout
   - Retry with jittered backoff
   - Circuit breaker

4. **Stop**:
   - Explicit stop or idle eviction triggers graceful shutdown

---

## 📊 Observability & Resilience

- **Logging**:
  - JSON logs: `alias`, `transport`, `latency_ms`, pool events
- **Metrics**:
  - OTEL-ready counters + histograms
- **Resilience**:
  - Per-call timeout
  - Retry w/ capped exponential backoff
  - Circuit breaker (half-open mode supported)

---

## 🔐 Security & Sandbox

- Secrets are passed via `env:` references, never hardcoded
- Runner creation requires:
  - Allowed command prefix
  - Explicit working dir
- Container security (planned):
  - Non-root defaults
  - File mount policies
  - Memory/CPU caps

---

## 🗺️ Roadmap

| Sprint | Deliverables |
|--------|--------------|
| **1** | Stdio runner, config, lifecycle, tool_bus, LangChain adapter |
| **2** | HTTP/SSE runner, OTEL spans, richer metrics |
| **3** | Container runner, AutoGen adapter, CLI |
| **4** | Security hardening, CI matrix, operator docs |

---

## ❓ Open Questions

- Default MCP client: native `mcp` vs `fastmcp`?
- Registry reload trigger: CLI/SIGHUP or REST/Web UI?
- LangChain export: legacy tools vs LCEL?

---

## 📘 Related Docs

- `REGISTRY_MERGE.md` – How MCP tools are declared and merged
- `TOOLS.md` – Tool structure and contract
- `AGENT-CORE.md` – How MCP tools are invoked via PlanStep execution

---

🔁 Return to [Agents.md](../AGENTS.md)
