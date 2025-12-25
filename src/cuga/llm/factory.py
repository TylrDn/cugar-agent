import os
from typing import Optional

from .budget import BudgetManager, budget_from_env
from .hybrid import HybridLLMClient, Policy
from .openai_like import OpenAILikeClient, azure_headers
from .types import ChatMessage
from ..config import load_llm_settings, LLMSettings


def _client_from_settings(settings: LLMSettings, env: dict) -> OpenAILikeClient:
    base_url = settings.base_url or env.get("AZURE_OPENAI_ENDPOINT", "")
    headers = azure_headers(settings.api_key) if env.get("AZURE_OPENAI_ENDPOINT") else None
    return OpenAILikeClient(
        model=settings.model,
        api_key=settings.api_key or None,
        base_url=base_url,
        timeout_s=settings.timeout_s,
        max_retries=settings.max_retries,
        api_version=env.get("AZURE_OPENAI_API_VERSION"),
        headers=headers,
    )


def get_llm_client(env: Optional[dict] = None):
    env = env or os.environ
    llm_settings = load_llm_settings(env=env)
    budget = BudgetManager(budget_from_env(env))
    if llm_settings.fallback:
        policy_cfg = llm_settings.policy or {}
        policy = Policy(
            fallback_on_timeout=policy_cfg.get("fallback_on_timeout", True),
            fallback_on_context_overflow=policy_cfg.get("fallback_on_context_overflow", True),
            fallback_on_budget_exceeded=policy_cfg.get("fallback_on_budget_exceeded", False),
        )
        primary = _client_from_settings(llm_settings.primary or llm_settings, env)
        fallback = _client_from_settings(llm_settings.fallback, env)
        return HybridLLMClient(primary, fallback, policy, budget)
    return _client_from_settings(llm_settings, env)


__all__ = ["get_llm_client", "ChatMessage"]
