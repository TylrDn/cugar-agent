from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class MemoryRecord:
    text: str
    metadata: Dict[str, str]
