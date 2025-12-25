Profile assumptions: sandboxed Docker runners for MCP; no implicit network for slim profiles.

Profiles
| profile    | base image           | cpu | mem  | time_s | fs roots (ro/rw)                | network      | cache dirs          |
|------------|----------------------|-----|------|--------|---------------------------------|--------------|---------------------|
| py-slim    | python:3.12-slim     | 1   | 1Gi  | 300    | /workspace:ro, /workspace/output:rw | outbound off | /tmp/pip-cache      |
| py-full    | python:3.12-bullseye | 2   | 2Gi  | 600    | /workspace:ro, /workspace/output:rw | outbound on  | /tmp/pip-cache      |
| node-slim  | node:20-slim         | 1   | 1Gi  | 300    | /workspace:ro, /workspace/output:rw | outbound off | /tmp/npm-cache      |
| node-full  | node:20-bullseye     | 2   | 2Gi  | 600    | /workspace:ro, /workspace/output:rw | outbound on  | /tmp/npm-cache      |

docker-compose mapping
| profile   | compose service key |
|-----------|---------------------|
| py-slim   | mcp.fs              |
| py-full   | mcp.e2b             |
| node-slim | mcp.web             |
| node-full | mcp.web             |
