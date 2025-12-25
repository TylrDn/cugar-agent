# Sandbox Profiles

Canonical profiles: `py-slim`, `py-full`, `node-slim`, `node-full`. Slim = no outbound network; full = outbound allowed for declared tools only.

Table 1: resources and mounts
| profile    | base image           | cpu | mem  | time_s | fs mounts (ro/rw)                    | network policy    | cache dirs        |
|-----------|----------------------|-----|------|--------|--------------------------------------|-------------------|-------------------|
| py-slim   | python:3.12-slim     | 1   | 1Gi  | 300    | /workspace:ro, /workspace/output:rw  | outbound denied   | /tmp/pip-cache    |
| py-full   | python:3.12-bullseye | 2   | 2Gi  | 600    | /workspace:ro, /workspace/output:rw  | outbound allowed  | /tmp/pip-cache    |
| node-slim | node:20-slim         | 1   | 1Gi  | 300    | /workspace:ro, /workspace/output:rw  | outbound denied   | /tmp/npm-cache    |
| node-full | node:20-bullseye     | 2   | 2Gi  | 600    | /workspace:ro, /workspace/output:rw  | outbound allowed  | /tmp/npm-cache    |

Table 2: compose service mapping
| sandbox profile | compose service key |
|-----------------|---------------------|
| py-slim         | mcp.fs              |
| py-full         | mcp.e2b             |
| node-slim       | mcp.web-slim        |
| node-full       | mcp.web-full        |

`mcp.web` profile selection: Option A (preferred) run `mcp.web-slim` by default and switch to `mcp.web-full` by enabling the `web-full` profile or setting `WEB_SERVICE=mcp.web-full` in compose. Option B use a single `mcp.web` service with an env toggle such as `WEB_PROFILE=node-slim|node-full`.
