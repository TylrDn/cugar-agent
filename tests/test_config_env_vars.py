from __future__ import annotations

import pytest

from cuga.modular.config import AgentConfig


def test_env_parsing_clamps_and_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLANNER_MAX_STEPS", "1000")
    monkeypatch.setenv("MODEL_TEMPERATURE", "-5")
    config = AgentConfig.from_env()
    assert config.max_steps == 50
    assert config.temperature == 0.0

    monkeypatch.setenv("PLANNER_MAX_STEPS", "bad")
    monkeypatch.setenv("MODEL_TEMPERATURE", "bad")
    config = AgentConfig.from_env()
    assert config.max_steps == 6
    assert config.temperature == 0.3
