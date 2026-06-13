"""Local text/image embeddings — bge-small (text) / CLIP (image). NO API.

STATUS: STUB with a deterministic offline fallback so the pipeline and tests
run without downloading any model.

Maddie: replace `_hash_embed` with a real local sentence-transformers load:

    from sentence_transformers import SentenceTransformer
    _model = SentenceTransformer(EMBED.text_model)   # cached locally after first run
    return _model.encode(text, normalize_embeddings=True).tolist()

Keep the public signature identical so retrieve.py / the pipeline don't change.
Precompute item vectors once and cache them — do NOT embed the whole catalog
on every request (demo-speed constraint).
"""
from __future__ import annotations

import hashlib

from .config import EMBED


def _hash_embed(text: str, dim: int) -> list[float]:
    """Deterministic pseudo-embedding for offline dev/testing only.

    Bag-of-words hashed into `dim` buckets. NOT semantically meaningful — it
    exists purely so the rest of the pipeline is exercisable before the real
    model is wired in. Replace with bge-small (see module docstring).
    """
    vec = [0.0] * dim
    for token in text.lower().split():
        h = int(hashlib.md5(token.encode()).hexdigest(), 16)
        vec[h % dim] += 1.0
    return vec


def embed_text(text: str) -> list[float]:
    """Embed a text blob to a fixed-dim vector. Local-only."""
    return _hash_embed(text or "", EMBED.dim)


def embed_catalog(texts: dict[str, str]) -> dict[str, list[float]]:
    """Precompute item vectors: {sku_id: text} -> {sku_id: vector}.

    Call this once at startup and cache the result.
    """
    return {sku_id: embed_text(text) for sku_id, text in texts.items()}
