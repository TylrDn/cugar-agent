# Tools

Custom tool definitions live in `src/cuga/modular/tools.py` and can wrap MCP servers or LangChain tools.

- Define tools via `ToolSpec` (name, description, schema, handler).
- Register them in `ToolRegistry` or load from `configs/tools.yaml`.
- Use `examples/run_langgraph_demo.py` to see tool execution traces.
