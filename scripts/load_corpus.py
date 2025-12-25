from __future__ import annotations

import argparse
from pathlib import Path
from cuga.modular.rag import RagLoader


def main() -> None:
    parser = argparse.ArgumentParser(description="Load documents into the configured vector backend")
    parser.add_argument("--source", default="rag/sources", help="Directory containing text/markdown files")
    parser.add_argument("--backend", default=None, help="Override vector backend")
    args = parser.parse_args()

    loader = RagLoader(backend=args.backend)
    files = list(Path(args.source).glob("**/*"))
    added = loader.ingest(files)
    print(f"Loaded {added} documents from {args.source}")


if __name__ == "__main__":
    main()
