from __future__ import annotations

import pytest

from cuga.modular.tools import ToolRegistry, ToolSpec, _load_handler


def test_dynamic_import_restricted() -> None:
    with pytest.raises(ImportError):
        _load_handler("os.path.join")


def test_dynamic_import_valid_handler() -> None:
    handler = _load_handler("cuga.modular.tools.echo")
    registry = ToolRegistry([ToolSpec(name="echo", description="", handler=handler)])
    assert registry.get("echo") is not None
