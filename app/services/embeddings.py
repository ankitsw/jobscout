from __future__ import annotations

import hashlib
import logging
import math
from functools import lru_cache

log = logging.getLogger(__name__)

_DIMENSIONS = 384
# Same weights as sentence-transformers' all-MiniLM-L6-v2, served through
# ONNX Runtime via fastembed. Identical 384-d output, but no PyTorch: the
# process peaks around 300 MB instead of exceeding Render's 512 MB limit.
_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def _load_model():
    try:
        from fastembed import TextEmbedding
        return TextEmbedding(model_name=_MODEL_NAME)
    except Exception:
        log.exception("embedding model unavailable, using hashed fallback")
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
    vector = next(iter(model.embed([text])))
    norm = float(math.sqrt(sum(float(v) * float(v) for v in vector))) or 1.0
    return [float(v) / norm for v in vector]
