from __future__ import annotations

from dataclasses import dataclass
import importlib
from typing import Any, Dict


class BaseEmitter:
    def emit(self, payload: Dict[str, Any]) -> None:  # pragma: no cover - interface
        raise NotImplementedError


@dataclass
class LangfuseEmitter(BaseEmitter):
    def emit(self, payload: Dict[str, Any]) -> None:
        if importlib.util.find_spec("langfuse") is None:  # type: ignore[attr-defined]
            return
        langfuse = importlib.import_module("langfuse")
        client = langfuse.Langfuse()
        client.trace(name=payload.get("event", "event"), input=payload)


@dataclass
class OpenInferenceEmitter(BaseEmitter):
    def emit(self, payload: Dict[str, Any]) -> None:
        if importlib.util.find_spec("openinference") is None:  # type: ignore[attr-defined]
            return
        openinference = importlib.import_module("openinference")  # type: ignore
        _ = openinference
        return None
