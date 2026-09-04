from __future__ import annotations

import hashlib
import math
from functools import lru_cache

_DIMENSIONS = 384


@lru_cache(maxsize=1)
def _load_model():
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer("all-MiniLM-L6-v2")
    except Exception:
        return None


def _fallback_embedding(text: str) -> list[float]:
    values = [0.0] * _DIMENSIONS
    for token in text.lower().split():
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % _DIMENSIONS
        values[index] += 1.0 if digest[4] % 2 else -1.0
    norm = math.sqrt(sum(value * value for value in values)) or 1.0
    return [value / norm for value in values]


def embed(text: str) -> list[float]:
    model = _load_model()
    if model is None:
        return _fallback_embedding(text)
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist()
