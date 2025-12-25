from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from cuga.mcp_servers._shared import RequestError, get_sandbox, run_main


PATTERNS = [
    {"name": "research-assistant", "description": "Plans web and document research tasks."},
    {"name": "summarizer", "description": "Condenses long-form content into concise notes."},
    {"name": "planner", "description": "Generates structured plans for multi-step goals."},
]


def _list_patterns() -> Dict[str, Any]:
    _ = get_sandbox()
    return {"patterns": PATTERNS}


def _generate_plan(params: Dict[str, Any]) -> Dict[str, Any]:
    _ = get_sandbox()
    goal = params.get("goal")
    if not isinstance(goal, str) or not goal.strip():
        raise RequestError("'goal' is required", details={"field": "goal"})
    steps: List[Dict[str, Any]] = []
    steps.append({"step": 1, "action": "analyze_goal", "detail": goal})
    steps.append({"step": 2, "action": "select_tools", "detail": params.get("tools", [])})
    steps.append({"step": 3, "action": "deliver_plan", "detail": "Return structured plan"})
    return {"plan": {"goal": goal, "steps": steps, "sandboxed": True}}


def _handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    method = payload.get("method")
    params = payload.get("params", {}) if isinstance(payload.get("params", {}), dict) else {}
    if method == "health":
        return {"ok": True, "result": {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}}
    if method != "run":
        raise RequestError("Unsupported method", details={"method": method})
    action = params.get("action")
    if action == "list_patterns":
        result = _list_patterns()
    elif action == "generate_plan":
        result = _generate_plan(params.get("params", {}) if isinstance(params.get("params", {}), dict) else {})
    else:
        raise RequestError("Unsupported action", details={"action": action})
    return {"ok": True, "result": result, "meta": {"tool": "moon_agents", "action": action}}


def main() -> None:
    run_main(_handle)


if __name__ == "__main__":
    main()
