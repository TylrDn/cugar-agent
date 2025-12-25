from __future__ import annotations

import pytest

from cuga.modular.rag import RagLoader


def test_backend_validation_errors() -> None:
    with pytest.raises(RuntimeError):
        RagLoader(backend="nonexistent")
