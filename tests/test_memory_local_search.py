from __future__ import annotations

from cuga.modular.memory import VectorMemory


def test_local_search_whole_word_matching() -> None:
    memory = VectorMemory(profile="local", backend_name="local")
    memory.remember("Alpha beta gamma", metadata={"path": "p1"})
    memory.remember("Unrelated text", metadata={"path": "p2"})
    results = memory.search("beta", top_k=3)
    assert len(results) == 1
    assert results[0].metadata["path"] == "p1"
    assert results[0].score > 0
