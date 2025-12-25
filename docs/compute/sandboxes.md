# Sandboxed Execution Profiles

Canonical sandbox profiles are designed for MCP-first adapters with least privilege. Default network is isolated unless noted.

## Profile Specs
| profile | base image | cpu | mem | time | fs mounts (ro/rw) | network policy | cache dirs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| py-slim | python:3.12-slim | 1 | 1GiB | 5m | /workspace:ro; profile-specific :rw overlays | isolated | /workspace/cache |
| py-full | python:3.12 | 2 | 2GiB | 15m | /workspace:ro; /workspace/artifacts:rw; tool-specific mounts | restricted egress | /workspace/cache |
| node-slim | node:20-slim | 1 | 1GiB | 5m | /workspace:ro | isolated | /workspace/.npm |
| node-full | node:20 | 2 | 2GiB | 10m | /workspace:ro; /workspace/artifacts:rw | restricted egress | /workspace/.npm |

## Profile → Compose Service
| sandbox profile | docker-compose service key |
| --- | --- |
| py-slim | mcp.fs |
| py-full | mcp.e2b |
| node-slim | mcp.web-slim (Option A) or mcp.web (Option B) |
| node-full | mcp.web-full (Option A) or mcp.web (Option B) |

### mcp.web profile selection
- **Option A (preferred):** run two services `mcp.web-slim` and `mcp.web-full`; set the registry entry's `sandbox` to the matching profile to select the service.
- **Option B:** single service `mcp.web` with `WEB_PROFILE=node-slim|node-full` env selecting the node image; ensure registry and compose agree on the active profile.
