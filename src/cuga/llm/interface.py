from typing import Protocol, Sequence

from .types import ChatMessage, ChatResponse


class LLMClient(Protocol):
    def chat(self, messages: Sequence[ChatMessage], **kwargs) -> ChatResponse:  # pragma: no cover - protocol signature
        ...
