from typing import Dict, Optional, Sequence

import litellm

from .interface import LLMClient
from .types import ChatMessage, ChatResponse, Usage


class LiteLLMClient(LLMClient):
    """LLM client backed by LiteLLM for routing and retries."""

    def __init__(
        self,
        model: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout_s: float = 60,
        max_retries: int = 3,
        api_version: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        fallbacks: Optional[list[str]] = None,
    ):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url or None
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.api_version = api_version
        self.headers = headers or {}
        self.fallbacks = fallbacks or []

    def chat(self, messages: Sequence[ChatMessage], **kwargs) -> ChatResponse:
        payload_model = kwargs.get("model", self.model)
        response = litellm.completion(
            model=payload_model,
            messages=[m.__dict__ for m in messages],
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout_s,
            api_version=self.api_version,
            max_retries=self.max_retries,
            headers=self.headers,
            fallbacks=self.fallbacks,
            **{k: v for k, v in kwargs.items() if k not in {"model"}},
        )
        usage_data = getattr(response, "usage", None) or response.get("usage", {})
        usage = Usage(
            prompt_tokens=usage_data.get("prompt_tokens", 0),
            completion_tokens=usage_data.get("completion_tokens", 0),
        )
        choice = response["choices"][0]["message"] if isinstance(response, dict) else response.choices[0].message
        content = choice.get("content") if isinstance(choice, dict) else getattr(choice, "content", "")
        raw = response if isinstance(response, dict) else response.model_dump()
        return ChatResponse(content=content or "", usage=usage, model=response.get("model", payload_model) if isinstance(response, dict) else getattr(response, "model", payload_model), raw=raw)
