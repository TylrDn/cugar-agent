# Agents

This directory documents modular agent roles available in `src/cuga/modular/agents.py` and examples under `examples/`.

- **PlannerAgent**: ReAct/Plan-and-Execute planner using registry snapshots and profile-aware metadata.
- **WorkerAgent**: Executes planner steps via the `ToolRegistry`, emitting structured traces.
- **CoordinatorAgent**: Orchestrates multi-agent workflows (CrewAI/AutoGen style) with shared vector memory summaries.
- **ObserverAgent**: Connects Langfuse/OpenInference emitters for traces.

See `USAGE.md` for CLI flows and `examples/multi_agent_dispatch.py` for coordination patterns.
