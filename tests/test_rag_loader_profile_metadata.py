from __future__ import annotations

from pathlib import Path

from cuga.modular.rag import RagLoader


def test_rag_ingest_stores_profile_metadata(tmp_path: Path) -> None:
    file_path = tmp_path / "doc.txt"
    file_path.write_text("hello world")
    loader = RagLoader(profile="profile1")
    loader.ingest([file_path])
    hit = loader.memory.store[0]
    assert hit.metadata["profile"] == "profile1"
    assert hit.metadata["path"] == str(file_path)
