# Memory

Vector memory connectors and summarization hooks are implemented in `src/cuga/modular/memory.py`.

- Backends: chroma, qdrant, weaviate, milvus, or an in-memory fallback.
- Namespaced by profile to respect sandbox boundaries.
- Configure via `configs/memory.yaml` or environment variables (see `.env.example`).
