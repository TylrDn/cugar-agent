from __future__ import annotations

import pathlib
from typing import Optional

from cuga.mcp.config import MCPConfig, load_config


def discover_from_path(path: str) -> MCPConfig:
    resolved = pathlib.Path(path).expanduser().resolve()
    return load_config(str(resolved))


def discover_default() -> MCPConfig:
    return load_config()

