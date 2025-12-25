import time
from typing import Dict, Optional, Sequence

import httpx

from .interface import LLMClient
from .types import ChatMessage, ChatResponse, Usage

DEFAULT_BASE_URL = "https://api.openai.com"


def azure_headers(api_key: Optional[str]) -> Dict[str, str]:
    return {"api-key": api_key} if api_key else {}


class OpenAILikeClient(LLMClient):
    def __init__(self, model: str, api_key: Optional[str] = None, base_url: str = "", timeout_s: float = 60, max_retries: int = 3, api_version: Optional[str] = None, headers: Optional[Dict[str, str]] = None):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url or DEFAULT_BASE_URL
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.api_version = api_version
        self.headers = headers or {}

    def _post(self, payload: Dict[str, object]) -> httpx.Response:
        url = f"{self.base_url.rstrip('/')}/v1/chat/completions"
        headers = {"Content-Type": "application/json", **self.headers}
        if self.api_key:
            headers.setdefault("Authorization", f"Bearer {self.api_key}")
        params = {"api-version": self.api_version} if self.api_version else None
        for attempt in range(self.max_retries + 1):
            try:
                return httpx.post(url, json=payload, headers=headers, params=params, timeout=self.timeout_s)
            except httpx.TimeoutException as exc:  # pragma: no cover
                if attempt == self.max_retries:
                    raise exc
                time.sleep(min(1.0, 0.1 * (2**attempt)))
        raise TimeoutError("LLM request failed")

    def chat(self, messages: Sequence[ChatMessage], **kwargs) -> ChatResponse:
        payload = {"model": kwargs.get("model", self.model), "messages": [m.__dict__ for m in messages], "temperature": kwargs.get("temperature", 0)}
        if kwargs.get("max_tokens") is not None:
            payload["max_tokens"] = kwargs["max_tokens"]
        response = self._post(payload)
        response.raise_for_status()
        data = response.json()
        usage_data = data.get("usage", {})
        usage = Usage(prompt_tokens=usage_data.get("prompt_tokens", 0), completion_tokens=usage_data.get("completion_tokens", 0))
        content = data["choices"][0]["message"].get("content", "")
        return ChatResponse(content=content, usage=usage, model=data.get("model", payload["model"]), raw=data)
