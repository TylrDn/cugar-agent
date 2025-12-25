from __future__ import annotations

import argparse
from cuga.modular.rag import RagRetriever


def main() -> None:
    parser = argparse.ArgumentParser(description="Query documents with the configured vector backend")
    parser.add_argument("--query", required=True)
    parser.add_argument("--backend", default=None, help="Override backend (chroma|qdrant|weaviate|milvus|local)")
    args = parser.parse_args()

    retriever = RagRetriever(backend=args.backend)
    results = retriever.query(args.query)
    for idx, hit in enumerate(results, start=1):
        print(f"{idx}. score={hit.score:.3f} text={hit.text[:120]}")


if __name__ == "__main__":
    main()
