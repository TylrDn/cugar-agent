"""MCP audit logging with append-only JSONL, cost tracking, and field redaction."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class MCPAuditRecord:
    """Single audit record for an MCP tool invocation."""

    timestamp: float = field(default_factory=time.time)
    trace_id: str = ""
    tool_id: str = ""
    tool_tier: int = 1
    method: str = ""
    input: Dict[str, Any] = field(default_factory=dict)
    output: Optional[Any] = None
    status: str = "pending"  # pending, success, error
    error: Optional[str] = None
    duration_ms: float = 0.0
    cost: float = 0.0
    latency: float = 0.0
    profile: str = "default"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    def redact_sensitive_fields(self, sensitive_keys: Optional[Set[str]] = None) -> None:
        """Redact sensitive fields from input/output/metadata."""
        if sensitive_keys is None:
            sensitive_keys = {"token", "secret", "password", "api_key", "apikey", "key"}

        def _redact_dict(d: Dict[str, Any]) -> None:
            for key in list(d.keys()):
                if any(sensitive in key.lower() for sensitive in sensitive_keys):
                    d[key] = "[REDACTED]"
                elif isinstance(d[key], dict):
                    _redact_dict(d[key])
                elif isinstance(d[key], list):
                    for item in d[key]:
                        if isinstance(item, dict):
                            _redact_dict(item)

        if isinstance(self.input, dict):
            _redact_dict(self.input)
        if isinstance(self.output, dict):
            _redact_dict(self.output)
        if isinstance(self.metadata, dict):
            _redact_dict(self.metadata)


class MCPAuditLogger:
    """
    Append-only JSONL audit logger for MCP tool invocations.
    Non-blocking, with automatic redaction of sensitive fields.
    """

    def __init__(
        self,
        audit_file: Optional[Path] = None,
        redact_sensitive: bool = True,
        auto_flush: bool = True,
    ):
        """
        Initialize the audit logger.

        Args:
            audit_file: Path to JSONL audit file. Defaults to logs/mcp_audit.jsonl
            redact_sensitive: If True, redact sensitive fields before logging
            auto_flush: If True, flush after each write
        """
        if audit_file is None:
            logs_dir = Path("logs")
            logs_dir.mkdir(parents=True, exist_ok=True)
            audit_file = logs_dir / "mcp_audit.jsonl"

        self.audit_file = audit_file
        self.redact_sensitive = redact_sensitive
        self.auto_flush = auto_flush
        self._ensure_file_exists()

    def _ensure_file_exists(self) -> None:
        """Ensure the audit file and parent directories exist."""
        self.audit_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.audit_file.exists():
            self.audit_file.touch()

    def log(self, record: MCPAuditRecord) -> None:
        """
        Log an audit record to the JSONL file.
        Non-blocking - exceptions are logged but not raised.
        """
        try:
            if self.redact_sensitive:
                record.redact_sensitive_fields()

            record_dict = record.to_dict()
            record_json = json.dumps(record_dict, separators=(",", ":"))

            with open(self.audit_file, "a", encoding="utf-8") as f:
                f.write(record_json + "\n")
                if self.auto_flush:
                    f.flush()

        except Exception as e:
            # Non-blocking: log error but don't raise
            logger.error(f"Failed to write audit log: {e}")

    def log_invocation(
        self,
        tool_id: str,
        method: str,
        input: Dict[str, Any],
        trace_id: str = "",
        profile: str = "default",
        tier: int = 1,
        **metadata: Any,
    ) -> MCPAuditRecord:
        """
        Log the start of a tool invocation.
        Returns the audit record for updating after completion.
        """
        record = MCPAuditRecord(
            trace_id=trace_id,
            tool_id=tool_id,
            tool_tier=tier,
            method=method,
            input=input.copy(),  # Defensive copy
            profile=profile,
            metadata=metadata,
        )
        self.log(record)
        return record

    def log_completion(
        self,
        record: MCPAuditRecord,
        output: Any,
        duration_ms: float,
        cost: float = 0.0,
        latency: float = 0.0,
    ) -> None:
        """Log successful completion of a tool invocation."""
        record.status = "success"
        record.output = output
        record.duration_ms = duration_ms
        record.cost = cost
        record.latency = latency
        self.log(record)

    def log_error(
        self,
        record: MCPAuditRecord,
        error: str,
        duration_ms: float,
    ) -> None:
        """Log failed tool invocation."""
        record.status = "error"
        record.error = error
        record.duration_ms = duration_ms
        self.log(record)

    def read_all(self) -> List[MCPAuditRecord]:
        """
        Read all audit records from the file.
        Useful for analysis and debugging.
        """
        records: List[MCPAuditRecord] = []

        if not self.audit_file.exists():
            return records

        try:
            with open(self.audit_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        record = MCPAuditRecord(**data)
                        records.append(record)
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.warning(f"Failed to parse audit record: {e}")
                        continue

        except Exception as e:
            logger.error(f"Failed to read audit log: {e}")

        return records

    def get_statistics(self) -> Dict[str, Any]:
        """Get summary statistics from audit log."""
        records = self.read_all()

        if not records:
            return {"total_invocations": 0}

        total = len(records)
        successful = sum(1 for r in records if r.status == "success")
        failed = sum(1 for r in records if r.status == "error")
        total_cost = sum(r.cost for r in records)
        total_duration = sum(r.duration_ms for r in records)
        avg_duration = total_duration / total if total > 0 else 0.0

        # Count by tool
        tools: Dict[str, int] = {}
        for r in records:
            tools[r.tool_id] = tools.get(r.tool_id, 0) + 1

        # Count by tier
        tiers: Dict[int, int] = {}
        for r in records:
            tiers[r.tool_tier] = tiers.get(r.tool_tier, 0) + 1

        return {
            "total_invocations": total,
            "successful": successful,
            "failed": failed,
            "success_rate": successful / total if total > 0 else 0.0,
            "total_cost": total_cost,
            "total_duration_ms": total_duration,
            "avg_duration_ms": avg_duration,
            "tools": dict(sorted(tools.items())),
            "tiers": dict(sorted(tiers.items())),
        }


# Global audit logger instance
_global_audit_logger: Optional[MCPAuditLogger] = None


def get_audit_logger(audit_file: Optional[Path] = None) -> MCPAuditLogger:
    """Get or create the global audit logger instance."""
    global _global_audit_logger
    if _global_audit_logger is None:
        _global_audit_logger = MCPAuditLogger(audit_file=audit_file)
    return _global_audit_logger


def normalize_output(output: Any) -> Any:
    """
    Normalize output for deterministic comparisons in tests.
    - Sort dict keys
    - Remove/normalize timestamps
    - Sort lists where order doesn't matter
    """
    if isinstance(output, dict):
        normalized = {}
        for key, value in sorted(output.items()):
            # Skip timestamp fields for determinism
            if key.lower() in {"timestamp", "created_at", "updated_at", "time"}:
                continue
            normalized[key] = normalize_output(value)
        return normalized
    elif isinstance(output, list):
        # Normalize each item
        return [normalize_output(item) for item in output]
    else:
        return output
