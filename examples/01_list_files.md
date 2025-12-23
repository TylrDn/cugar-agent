# Example: local stdio MCP echo server

This example uses the built-in stdio runner and the sample `tests/mcp/echo_server.py` command.

```bash
# Start a call via the tool bus
python - <<'PY'
import asyncio
from cuga.mcp.tool_bus import ToolBus

async def main():
    bus = ToolBus()
    resp = await bus.call("echo", "echo", {"value": "demo"})
    print(resp)
    await bus.lifecycle.stop_all()

asyncio.run(main())
PY
```
