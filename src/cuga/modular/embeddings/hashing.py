from __future__ import annotations

import hashlib
from typing import Final

_DIM: Final = 64


class HashingEmbedder:
    """Deterministic offline embedder using hashing."""

    def embed(self, text: str) -> list[float]:
        tokens = text.lower().split()
        vector = [0.0 for _ in range(_DIM)]
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            idx = digest[0] % _DIM
            vector[idx] += 1.0
        norm = sum(v * v for v in vector) ** 0.5
        if norm > 0:
            vector = [v / norm for v in vector]
        return vector
