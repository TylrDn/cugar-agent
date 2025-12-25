from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def test_cli_ingest_and_query(tmp_path: Path) -> None:
    doc = tmp_path / "doc.txt"
    doc.write_text("hello modular world")
    state = tmp_path / "state.json"

    env = {**os.environ, "PYTHONPATH": str(Path.cwd() / "src")}
    subprocess.check_call(
        [sys.executable, "-m", "cuga.modular.cli", "--state", str(state), "ingest", str(doc)],
        cwd=Path.cwd(),
        env=env,
    )
    output = subprocess.check_output(
        [sys.executable, "-m", "cuga.modular.cli", "--state", str(state), "query", "hello"],
        cwd=Path.cwd(),
        env=env,
    )
    line = output.decode().strip().splitlines()[-1]
    payload = json.loads(line)
    assert payload["event"] == "query"
