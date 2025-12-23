from __future__ import annotations

import json
import logging
import sys
from typing import Any, Dict


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
        base: Dict[str, Any] = {
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "module": record.module,
        }
        if record.args:
            base["args"] = record.args
        if hasattr(record, "extra_fields"):
            base.update(getattr(record, "extra_fields"))
        return json.dumps(base)


def setup_json_logging(level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger("cuga.mcp")
    logger.setLevel(level)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.handlers = [handler]
    logger.propagate = False
    return logger
