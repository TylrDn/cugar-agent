from dataclasses import dataclass
from typing import Sequence

import httpx

from .budget import BudgetExceeded, BudgetManager
from .interface import LLMClient
from .types import ChatMessage, ChatResponse


@dataclass
class Policy:
    fallback_on_timeout: bool = True
    fallback_on_context_overflow: bool = True
    fallback_on_budget_exceeded: bool = False


class HybridLLMClient(LLMClient):
    def __init__(self, primary: LLMClient, fallback: LLMClient, policy: Policy, budget: BudgetManager):
        self.primary = primary
        self.fallback = fallback
        self.policy = policy
        self.budget = budget

    def _record(self, response: ChatResponse, is_local: bool) -> ChatResponse:
        response.cost = self.budget.record(response.usage, response.model, is_local)
        return response

    def chat(self, messages: Sequence[ChatMessage], **kwargs) -> ChatResponse:
        try:
            primary_response = self.primary.chat(messages, **kwargs)
            return self._record(
                primary_response,
                is_local=not getattr(self.primary, "api_key", None),
            )
        except httpx.TimeoutException:
            if not self.policy.fallback_on_timeout:
                raise
        except BudgetExceeded:
            if not self.policy.fallback_on_budget_exceeded:
                raise
        except ValueError as exc:
            if "context" not in str(exc) or not self.policy.fallback_on_context_overflow:
                raise
        except Exception:
            # Catch other primary client errors and attempt fallback
            pass

        try:
            fallback_response = self.fallback.chat(messages, **kwargs)
            return self._record(fallback_response, is_local=False)
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("LLM fallback client also failed") from exc

