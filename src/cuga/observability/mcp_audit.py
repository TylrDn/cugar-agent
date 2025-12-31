"""MCP audit logging with JSONL format and sensitive field redaction.

This module provides non-blocking, append-only audit logging for MCP tool
execution with automatic redaction of sensitive fields and cost tracking.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# Fields that should be redacted in audit logs
SENSITIVE_FIELDS = {
    "secret",
    "token",
    "password",
    "api_key",
    "apikey",
    "auth",
    "credential",
    "key",
}


class MCPAuditLogger:
    """Non-blocking JSONL audit logger for MCP tool execution.
    
    Features:
    - Append-only JSONL format for easy parsing
    - Automatic timestamp and cost tracking
    - Sensitive field redaction
    - Non-blocking writes (buffered)
    - Output normalization for deterministic logs
    """
    
    def __init__(
        self,
        log_path: Optional[Path] = None,
        buffer_size: int = 1000,
        auto_flush: bool = True,
    ):
        """Initialize the audit logger.
        
        Args:
            log_path: Path to the audit log file. If None, logs to default location.
            buffer_size: Number of entries to buffer before flushing.
            auto_flush: Whether to auto-flush after each write.
        """
        self.log_path = log_path or self._default_log_path()
        self.buffer_size = buffer_size
        self.auto_flush = auto_flush
        self._buffer: List[str] = []
        self._total_cost = 0.0
        
        # Ensure log directory exists
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
    
    @staticmethod
    def _default_log_path() -> Path:
        """Get default audit log path."""
        return Path.cwd() / "logs" / "mcp_audit.jsonl"
    
    def log_execution(
        self,
        tool_id: str,
        inputs: Dict[str, Any],
        outputs: Optional[Dict[str, Any]] = None,
        status: str = "success",
        error: Optional[str] = None,
        duration_ms: Optional[float] = None,
        cost: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log a tool execution event.
        
        Args:
            tool_id: The tool identifier
            inputs: Tool input parameters (will be redacted)
            outputs: Tool output results (will be redacted)
            status: Execution status (success, error, timeout, etc.)
            error: Error message if status is error
            duration_ms: Execution duration in milliseconds
            cost: Estimated cost of the operation
            metadata: Additional metadata (trace_id, user_id, etc.)
        """
        timestamp = datetime.utcnow().isoformat() + "Z"
        
        entry = {
            "timestamp": timestamp,
            "event": "tool_execution",
            "tool_id": tool_id,
            "status": status,
            "inputs": self._redact(inputs),
            "duration_ms": duration_ms,
            "cost": cost,
        }
        
        if outputs is not None:
            entry["outputs"] = self._normalize_output(self._redact(outputs))
        
        if error:
            entry["error"] = error
        
        if metadata:
            entry["metadata"] = self._redact(metadata)
        
        self._total_cost += cost
        entry["total_cost"] = round(self._total_cost, 6)
        
        self._write_entry(entry)
    
    def log_event(
        self,
        event_type: str,
        data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log a generic audit event.
        
        Args:
            event_type: Type of event (e.g., 'tool_load', 'guard_check')
            data: Event data
            metadata: Additional metadata
        """
        timestamp = datetime.utcnow().isoformat() + "Z"
        
        entry = {
            "timestamp": timestamp,
            "event": event_type,
            "data": self._redact(data),
        }
        
        if metadata:
            entry["metadata"] = self._redact(metadata)
        
        self._write_entry(entry)
    
    def _write_entry(self, entry: Dict[str, Any]) -> None:
        """Write an entry to the log buffer.
        
        Args:
            entry: The log entry to write
        """
        try:
            line = json.dumps(entry, sort_keys=True) + "\n"
            self._buffer.append(line)
            
            if self.auto_flush or len(self._buffer) >= self.buffer_size:
                self.flush()
        except Exception as e:
            logger.error(f"Failed to write audit entry: {e}")
    
    def flush(self) -> None:
        """Flush buffered entries to disk."""
        if not self._buffer:
            return
        
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.writelines(self._buffer)
            self._buffer.clear()
        except Exception as e:
            logger.error(f"Failed to flush audit log: {e}")
    
    def _redact(self, data: Any) -> Any:
        """Recursively redact sensitive fields from data.
        
        Args:
            data: Data to redact
            
        Returns:
            Redacted data
        """
        if isinstance(data, dict):
            redacted = {}
            for key, value in data.items():
                # Check if key contains sensitive terms
                if any(term in key.lower() for term in SENSITIVE_FIELDS):
                    redacted[key] = "[REDACTED]"
                else:
                    redacted[key] = self._redact(value)
            return redacted
        elif isinstance(data, list):
            return [self._redact(item) for item in data]
        elif isinstance(data, tuple):
            return tuple(self._redact(item) for item in data)
        else:
            return data
    
    def _normalize_output(self, data: Any) -> Any:
        """Normalize output for deterministic logging.
        
        Normalizations:
        - Sort dictionary keys
        - Round floating point numbers
        - Truncate very long strings
        
        Args:
            data: Data to normalize
            
        Returns:
            Normalized data
        """
        if isinstance(data, dict):
            return {k: self._normalize_output(v) for k, v in sorted(data.items())}
        elif isinstance(data, list):
            return [self._normalize_output(item) for item in data]
        elif isinstance(data, float):
            # Round to 6 decimal places for determinism
            return round(data, 6)
        elif isinstance(data, str):
            # Truncate very long strings
            max_len = 10000
            if len(data) > max_len:
                return data[:max_len] + f"... (truncated, {len(data)} total chars)"
            return data
        else:
            return data
    
    def get_total_cost(self) -> float:
        """Get total accumulated cost."""
        return round(self._total_cost, 6)
    
    def close(self) -> None:
        """Close the audit logger and flush remaining entries."""
        self.flush()


class AuditContext:
    """Context manager for audit logging with automatic timing.
    
    Example:
        >>> logger = MCPAuditLogger()
        >>> with AuditContext(logger, "mcp.github", {"repo": "example"}) as ctx:
        ...     result = do_work()
        ...     ctx.set_outputs({"status": "ok"})
    """
    
    def __init__(
        self,
        logger: MCPAuditLogger,
        tool_id: str,
        inputs: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Initialize audit context.
        
        Args:
            logger: The audit logger instance
            tool_id: Tool identifier
            inputs: Tool inputs
            metadata: Additional metadata
        """
        self.logger = logger
        self.tool_id = tool_id
        self.inputs = inputs
        self.metadata = metadata or {}
        self.outputs: Optional[Dict[str, Any]] = None
        self.status = "success"
        self.error: Optional[str] = None
        self.start_time: Optional[float] = None
        self.cost = 0.0
    
    def __enter__(self) -> AuditContext:
        """Enter the audit context."""
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit the audit context and log the execution."""
        duration_ms = None
        if self.start_time:
            duration_ms = (time.time() - self.start_time) * 1000
        
        if exc_type is not None:
            self.status = "error"
            self.error = f"{exc_type.__name__}: {exc_val}"
        
        self.logger.log_execution(
            tool_id=self.tool_id,
            inputs=self.inputs,
            outputs=self.outputs,
            status=self.status,
            error=self.error,
            duration_ms=duration_ms,
            cost=self.cost,
            metadata=self.metadata,
        )
    
    def set_outputs(self, outputs: Dict[str, Any]) -> None:
        """Set the outputs for this execution."""
        self.outputs = outputs
    
    def set_cost(self, cost: float) -> None:
        """Set the cost for this execution."""
        self.cost = cost
    
    def set_status(self, status: str) -> None:
        """Set the status for this execution."""
        self.status = status
    
    def set_error(self, error: str) -> None:
        """Set an error message."""
        self.error = error
        self.status = "error"


def create_audit_logger(
    log_path: Optional[Path] = None,
    auto_flush: bool = True,
) -> MCPAuditLogger:
    """Convenience function to create an audit logger.
    
    Args:
        log_path: Path to the audit log file
        auto_flush: Whether to auto-flush after each write
        
    Returns:
        MCPAuditLogger instance
    """
    return MCPAuditLogger(log_path=log_path, auto_flush=auto_flush)
