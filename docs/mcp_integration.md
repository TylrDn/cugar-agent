# MCP Integration Architecture

This document captures the first productionization slice for Model Context Protocol (MCP) server integrations inside CUGA. It
focuses on separation of concerns, lifecycle management, observability, and safe defaults that enable hot-swappable tools
usable by both the agent core and external orchestrators (LangChain/AutoGen).

## Goals and Non-Goals
- **Goals**: clear interfaces, registry-driven tool resolution, lifecycle management for MCP servers, structured telemetry,
  resilience (timeouts/backoff/breaker), and examples/tests that work without external network calls.
- **Non-Goals**: full feature parity with every MCP transport, long-running production control-plane, or shipping default
  secrets. Those belong to later sprints.

## Target Topology
```text
agent core -> tool_bus -> lifecycle manager -> runner (transport-specific)
                              ^                    |
                              |                    +-- subprocess stdio (default)
                              |                    +-- http/sse (planned)
                              |                    +-- container (planned)
                              |
                        registry/discovery -> config/entrypoints/files
```

### Key Components
- **Interfaces** (`cuga.mcp.interfaces`): typed request/response models and protocols for tools, runners, and registries.
- **Config** (`cuga.mcp.config`): Pydantic models for tool specs, transports, pooling, and security knobs. Supports TOML with
  environment variable overrides (`CUGA_MCP_CONFIG`).
- **Registry** (`cuga.mcp.registry`): in-memory store with semantic-version validation and hot-swap via discovery reload.
- **Lifecycle Manager** (`cuga.mcp.lifecycle`): start/stop/query MCP tools, reuse runners via a keyed pool, and wrap calls with
  retries/backoff/timeouts plus a basic circuit breaker.
- **Runners** (`cuga.mcp.runners.subprocess_stdio`): supervision for stdio subprocess MCP servers with bounded log capture and
  graceful shutdown. HTTP/SSE and container runners are stubbed for roadmap alignment.
- **Adapters** (`cuga.mcp.adapters.*`): expose MCP tools to the agent core (`tool_bus`) and interoperability layers
  (LangChain/AutoGen facades).
- **Telemetry** (`cuga.mcp.telemetry.*`): JSON logging and pluggable metrics hooks (OTEL-ready).

## Configuration Shape
TOML example (minimal):
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
Environment overrides (examples):
- `CUGA_MCP_CONFIG=/path/to/config.toml`
- `CUGA_MCP__TOOLS__ECHO__COMMAND=/custom/python`

## Lifecycle
1. **Resolve**: `tool_bus.call("echo", …)` asks the registry for the tool spec and performs semver validation.
2. **Ensure runner**: lifecycle manager reuses or spawns a runner keyed by tool+transport; applies pooling limits.
3. **Call**: requests are wrapped in timeouts + retry with jittered backoff; circuit breaker opens after repeated failures.
4. **Stop**: explicit stop or idle eviction shuts down runners gracefully, with a hard kill on timeout.

## Observability & Resilience
- JSON logs include `alias`, `transport`, `req_id`, `attempt`, `latency_ms`, and pool events.
- Metrics hooks emit counters/histograms and can be wired to OTEL; kept lightweight for offline tests.
- Resilience features: per-call timeout, retry with capped exponential backoff, and a simple half-open breaker state.

## Security & Sandbox
- Secrets are referenced only (e.g., `env:MY_TOKEN`); resolution occurs at runtime.
- Command/image allow-lists guard runner creation; paths/working directories are explicit.
- Future work: container isolation defaults, filesystem policy, non-root enforcement.

## Roadmap (incremental)
- **Sprint 1 (this slice)**: stdio runner, registry+config, lifecycle with pooling, tool bus, LangChain shim, docs, and unit
  tests against a local stdio MCP server.
- **Sprint 2**: HTTP/SSE runner, OTEL spans, richer pool metrics, and integration tests with SSE echo server.
- **Sprint 3**: Container runner with resource limits, AutoGen adapter, CLI orchestration, and golden log fixtures.
- **Sprint 4**: Security hardening (allow/deny lists, sandbox knobs), CI matrix (lint/type/test/container), and operator docs.

## Open Questions (to resolve next)
- Preferred default MCP client: native `mcp` vs. `fastmcp`? (Current slice uses stdlib JSON over stdio for local tests.)
- Should registry reload be wired to an existing control plane (REST/Web UI) or just SIGHUP/CLI for now?
- Which LangChain tool surface (legacy vs LCEL) should be the default export?
