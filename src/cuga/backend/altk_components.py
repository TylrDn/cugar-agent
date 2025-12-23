"""Integration wrappers for Agent Lifecycle Toolkit (ALTK).

This module exposes lightweight adapters that allow the core agent pipeline
to opt into ALTK processing without taking a hard dependency on any specific
component at call sites. Each wrapper performs defensive error handling so
that the main flow continues even if a lifecycle stage fails.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from loguru import logger

try:
    from altk.post_tool.silent_review import SilentReviewForJSONDataComponent
    from altk.pre_llm.spotlight import SpotlightComponent
    from altk.pre_response.policy_guard import PolicyGuardComponent
    from altk.pre_tool.refraction import RefractionComponent
except Exception as exc:  # pragma: no cover - optional dependency
    logger.warning("Agent Lifecycle Toolkit components unavailable: {}", exc)
    SilentReviewForJSONDataComponent = None  # type: ignore
    SpotlightComponent = None  # type: ignore
    PolicyGuardComponent = None  # type: ignore
    RefractionComponent = None  # type: ignore


class PromptEnhancer:
    """Wrapper around ALTK Spotlight for pre-LLM prompt improvement."""

    def __init__(self, component: Optional[Any] = None) -> None:
        self.component = component or (SpotlightComponent() if SpotlightComponent else None)

    def run(self, prompt: str) -> str:
        if not self.component:
            return prompt
        try:
            return self.component.process(prompt)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("Spotlight enhancement failed: {}", exc)
            return prompt


class ToolCallValidator:
    """Wrapper around ALTK Refraction for tool call validation/correction."""

    def __init__(self, component: Optional[Any] = None) -> None:
        self.component = component or (RefractionComponent() if RefractionComponent else None)

    def run(self, tool_call: Dict[str, Any]) -> Dict[str, Any]:
        if not self.component:
            return tool_call
        try:
            return self.component.process(tool_call)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("Refraction validation failed: {}", exc)
            return tool_call


class ToolOutputReviewer:
    """Wrapper around ALTK Silent Review for post-tool JSON validation."""

    def __init__(self, component: Optional[Any] = None) -> None:
        self.component = component or (
            SilentReviewForJSONDataComponent() if SilentReviewForJSONDataComponent else None
        )

    def run(self, output: Any) -> Dict[str, Any]:
        """Review tool output and return a structured assessment.

        Returns a dictionary so callers can decide whether to retry or attach
        the feedback to the agent state.
        """

        default_response = {"needs_retry": False, "details": None}
        if not self.component:
            return default_response
        try:
            review = self.component.process(output)
            if isinstance(review, dict):
                return {"needs_retry": review.get("retry", False), "details": review}
            return default_response
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("Silent review failed: {}", exc)
            return default_response


class PolicyGuardEnforcer:
    """Wrapper around ALTK PolicyGuard for pre-response enforcement."""

    def __init__(self, component: Optional[Any] = None) -> None:
        self.component = component or (PolicyGuardComponent() if PolicyGuardComponent else None)

    def run(self, response: str) -> str:
        if not self.component:
            return response
        try:
            return self.component.process(response)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("PolicyGuard enforcement failed: {}", exc)
            return response


class ALTKLifecycleManager:
    """Coordinator for ALTK components across the agent pipeline."""

    def __init__(
        self,
        prompt_enhancer: Optional[PromptEnhancer] = None,
        tool_validator: Optional[ToolCallValidator] = None,
        tool_reviewer: Optional[ToolOutputReviewer] = None,
        policy_guard: Optional[PolicyGuardEnforcer] = None,
        enabled: bool = False,
    ) -> None:
        self.enabled = enabled
        if not enabled:
            self.prompt_enhancer = None
            self.tool_validator = None
            self.tool_reviewer = None
            self.policy_guard = None
            return

        self.prompt_enhancer = prompt_enhancer or PromptEnhancer()
        self.tool_validator = tool_validator or ToolCallValidator()
        self.tool_reviewer = tool_reviewer or ToolOutputReviewer()
        self.policy_guard = policy_guard or PolicyGuardEnforcer()

    def enhance_state_prompt(self, state: Any) -> Any:
        if not (self.enabled and self.prompt_enhancer):
            return state
        if hasattr(state, "input") and state.input:
            original = state.input
            state.input = self.prompt_enhancer.run(str(state.input))
            logger.debug("Spotlight enhanced input from {} to {}", original, state.input)
        if hasattr(state, "goal") and state.goal:
            original = state.goal
            state.goal = self.prompt_enhancer.run(str(state.goal))
            logger.debug("Spotlight enhanced goal from {} to {}", original, state.goal)
        return state

    def validate_tool_calls(self, tool_calls: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
        if not (self.enabled and self.tool_validator and tool_calls):
            return tool_calls
        validated = []
        for call in tool_calls:
            validated.append(self.tool_validator.run(call))
        return validated

    def review_tool_outputs(self, output: Any) -> Optional[Dict[str, Any]]:
        if not (self.enabled and self.tool_reviewer):
            return None
        return self.tool_reviewer.run(output)

    def enforce_policy(self, response: Optional[str]) -> Optional[str]:
        if not (self.enabled and self.policy_guard and response):
            return response
        return self.policy_guard.run(response)

    @classmethod
    def from_settings(cls, enabled: bool) -> "ALTKLifecycleManager":
        return cls(enabled=enabled)

