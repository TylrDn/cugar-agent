from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence


@dataclass
class ChatMessage:
    role: str
    content: str


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class Cost:
    input_cost: float = 0.0
    output_cost: float = 0.0

    @property
    def total(self) -> float:
        return self.input_cost + self.output_cost


@dataclass
class ChatResponse:
    content: str
    usage: Usage
    model: str
    raw: Dict[str, Any]
    cost: Optional[Cost] = None


ChatMessages = Sequence[ChatMessage]
