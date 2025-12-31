"""Plan executor that isolates each subagent call."""

from __future__ import annotations

import copy
from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from cuga.orchestrator.protocol import ExecutionContext

from .planner import PlanStep
from .policy import PolicyEnforcer
from .registry import ToolRegistry

# Import MCP toolbox for MCP tool integration
try:
    from cuga.tools.mcp_toolbox import MCPToolbox
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False


@dataclass
class ExecutionResult:
    steps: List[Dict[str, Any]]
    output: Any | None = None
    trace: List[Any] | None = None


class Executor:
    """Executes a plan using tools from an isolated registry view."""

    def __init__(
        self, 
        policy_enforcer: PolicyEnforcer | None = None,
        mcp_toolbox: Optional["MCPToolbox"] = None,
        enable_mcp: bool = False,
        mcp_registry_path: Optional[Path] = None,
        mcp_allowed_tiers: Optional[List[int]] = None,
    ) -> None:
        self.policy_enforcer = policy_enforcer
        self.enable_mcp = enable_mcp and MCP_AVAILABLE
        self.mcp_toolbox = mcp_toolbox
        
        # Initialize MCP toolbox if enabled and not provided
        if self.enable_mcp and self.mcp_toolbox is None and MCP_AVAILABLE:
            from cuga.tools.mcp_toolbox import create_mcp_toolbox
            self.mcp_toolbox = create_mcp_toolbox(
                allowed_tiers=mcp_allowed_tiers or [1],
                registry_path=mcp_registry_path,
                deny_by_default=True,
            )

    @property
    def audit_logger(self) -> logging.Logger:
        return logging.getLogger("cuga.agents.audit")

    def _record_audit(self, trace: List[Any], record: Dict[str, Any]) -> None:
        """Append an audit record to the trace and emit it via the audit logger."""

        self.audit_logger.info("audit", extra={"audit": record})
        trace.append(record)

    def execute_plan(
        self,
        plan: Iterable[PlanStep],
        registry: ToolRegistry,
        context: ExecutionContext,
        trace: List[str] | None = None,
    ) -> ExecutionResult:
        step_results: List[Dict[str, Any]] = []
        metadata = context.metadata or {}
        if self.policy_enforcer is None:
            self.policy_enforcer = PolicyEnforcer()
        self.policy_enforcer.validate_metadata(context.profile, metadata)
        trace_entries: List[Any] = list(trace or [])
        for step in plan:
            self.policy_enforcer.validate_step(context.profile, step, metadata)
            
            # Try MCP toolbox first if enabled and tool has "mcp." prefix
            if self.enable_mcp and self.mcp_toolbox and step.tool.startswith("mcp."):
                result = self._execute_mcp_tool(step, context, trace_entries)
                step_results.append({"step": step.name, "tool": step.tool, "result": result})
                if result.get("status") == "failed":
                    return ExecutionResult(steps=step_results, output=result, trace=trace_entries)
                continue
            
            # Fall back to standard registry
            tool_entry = registry.resolve(context.profile, step.tool)
            handler = tool_entry["handler"]
            config = tool_entry.get("config", {})
            audit_record: Dict[str, Any] = {
                "event": "execute_step",
                "step": step.name,
                "profile": context.profile,
                "tool": step.tool,
                "input": step.input,
                "policy_decision": "allowed",
            }
            try:
                result = handler(step.input, config=copy.deepcopy(config), context=context)
                audit_record["status"] = "success"
                step_results.append({"step": step.name, "tool": step.tool, "result": result})
            except Exception as exc:  # noqa: BLE001
                audit_record.update({"status": "error", "error": type(exc).__name__})
                failure_payload = {"status": "failed", "reason": "handler_error"}
                step_results.append({"step": step.name, "tool": step.tool, "result": failure_payload})
                self._record_audit(trace_entries, audit_record)
                return ExecutionResult(steps=step_results, output=failure_payload, trace=trace_entries)
            self._record_audit(trace_entries, audit_record)
        final_output = step_results[-1]["result"] if step_results else None
        return ExecutionResult(steps=step_results, output=final_output, trace=trace_entries)
    
    def _execute_mcp_tool(
        self, step: PlanStep, context: ExecutionContext, trace: List[Any]
    ) -> Dict[str, Any]:
        """Execute an MCP tool with guard enforcement and audit logging."""
        audit_record: Dict[str, Any] = {
            "event": "execute_mcp_tool",
            "step": step.name,
            "profile": context.profile,
            "tool": step.tool,
            "input": step.input,
            "policy_decision": "allowed",
        }
        
        try:
            # Execute through MCP toolbox (includes guard and audit)
            result = self.mcp_toolbox.execute_tool(
                tool_id=step.tool,
                input=step.input,
                context={
                    "trace_id": context.trace_id,
                    "profile": context.profile,
                },
            )
            audit_record["status"] = "success"
            self._record_audit(trace, audit_record)
            return result
            
        except KeyError as exc:
            # Tool not found in MCP registry
            audit_record.update({"status": "error", "error": f"MCP tool not found: {exc}"})
            self._record_audit(trace, audit_record)
            return {"status": "failed", "reason": "mcp_tool_not_found", "error": str(exc)}
            
        except RuntimeError as exc:
            # Guard check failed
            audit_record.update({"status": "error", "error": f"Guard check failed: {exc}"})
            self._record_audit(trace, audit_record)
            return {"status": "failed", "reason": "guard_check_failed", "error": str(exc)}
            
        except Exception as exc:  # noqa: BLE001
            # Other execution error
            audit_record.update({"status": "error", "error": type(exc).__name__})
            self._record_audit(trace, audit_record)
            return {"status": "failed", "reason": "mcp_execution_error", "error": str(exc)}
