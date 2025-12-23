from __future__ import annotations

from typing import Any, Callable, Dict, Optional


class ValidationError(Exception):
    pass


class FieldInfo:
    def __init__(self, default: Any = None, default_factory: Optional[Callable[[], Any]] = None):
        self.default = default
        self.default_factory = default_factory


def Field(default: Any = None, default_factory: Optional[Callable[[], Any]] = None):  # type: ignore[N802]
    return FieldInfo(default=default, default_factory=default_factory)


class BaseModel:
    def __init__(self, **data: Any) -> None:
        annotations = getattr(self, "__annotations__", {})
        for name in annotations:
            if name in data:
                value = data[name]
            else:
                default = getattr(self.__class__, name, None)
                if isinstance(default, FieldInfo):
                    if default.default_factory is not None:
                        value = default.default_factory()
                    else:
                        value = default.default
                else:
                    value = default
            setattr(self, name, value)

    @classmethod
    def model_validate(cls, data: Dict[str, Any]) -> "BaseModel":
        try:
            return cls(**data)
        except Exception as exc:  # pragma: no cover - minimal stub
            raise ValidationError(str(exc)) from exc

    def model_dump(self) -> Dict[str, Any]:  # pragma: no cover - convenience
        return {key: getattr(self, key) for key in getattr(self, "__annotations__", {})}

