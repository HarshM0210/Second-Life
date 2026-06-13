"""Local text embeddings — bge-small-en-v1.5 via sentence-transformers. NO API.

Model is downloaded once on first use and cached locally. All embeddings are
L2-normalized (unit vectors) so cosine similarity == dot product.
"""
from __future__ import annotations

import hashlib
from typing import Optional

from .config import EMBED

_model = None


def _get_model():
    """Lazy-load the sentence-transformers model (cached after first download)."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(EMBED.text_model)
    return _model


def _hash_embed(text: str, dim: int) -> list[float]:
    """Deterministic pseudo-embedding fallback for offline/CI environments."""
    vec = [0.0] * dim
    for token in text.lower().split():
        h = int(hashlib.md5(token.encode()).hexdigest(), 16)
        vec[h % dim] += 1.0
    # Normalize
    norm = sum(x * x for x in vec) ** 0.5
    if norm > 0:
        vec = [x / norm for x in vec]
    return vec


def embed_text(text: str, use_model: Optional[bool] = None) -> list[float]:
    """Embed a text blob to a fixed-dim vector. Local-only, normalized.

    Args:
        text: input text.
        use_model: if False, force hash fallback. If None (default), try real
            model and fall back to hash if sentence-transformers unavailable.
    """
    if use_model is False:
        return _hash_embed(text or "", EMBED.dim)
    try:
        model = _get_model()
        vec = model.encode(text or "", normalize_embeddings=True)
        return vec.tolist()
    except Exception:
        return _hash_embed(text or "", EMBED.dim)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Batch embed multiple texts (much faster than one-by-one with the real model)."""
    if not texts:
        return []
    try:
        model = _get_model()
        vecs = model.encode(texts, normalize_embeddings=True, batch_size=64)
        return vecs.tolist()
    except Exception:
        return [_hash_embed(t, EMBED.dim) for t in texts]


def embed_catalog(texts: dict[str, str]) -> dict[str, list[float]]:
    """Precompute item vectors: {sku_id: text} -> {sku_id: vector}.

    Uses batch encoding for efficiency. Call once at startup and cache.
    """
    if not texts:
        return {}
    ids = list(texts.keys())
    blobs = [texts[i] for i in ids]
    vecs = embed_texts(blobs)
    return dict(zip(ids, vecs))
