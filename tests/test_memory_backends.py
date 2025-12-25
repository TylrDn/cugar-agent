import pytest

from cuga.modular.memory import VectorMemory


def test_memory_search_returns_matches():
    memory = VectorMemory(profile="unit")
    memory.remember("a small test string", metadata={"profile": "unit"})
    assert memory.search("test")


def test_backend_validation_failure():
    memory = VectorMemory(backend="unknown")
    with pytest.raises(RuntimeError):
        memory.connect_backend()
