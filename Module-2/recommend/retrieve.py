"""Pure cosine retrieval — the reusable core (per AGENTS.md / Module 5 contract).

This file contains NO recommendation business rules. Module 5 (P2P) wraps
`retrieve()` with a geo/distance filter, so it must stay pure: vectors in,
(sku_id, similarity) out. Boosting/badging lives in rerank.py, not here.
"""
from __future__ import annotations

import math
from typing import Sequence


Vector = Sequence[float]


def cosine_similarity(a: Vector, b: Vector) -> float:
    """Cosine similarity of two equal-length vectors. Returns 0.0 for a zero vector."""
    if len(a) != len(b):
        raise ValueError(f"vector length mismatch: {len(a)} != {len(b)}")
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def retrieve(
    user_vec: Vector,
    item_vecs: dict[str, Vector],
    k: int | None = None,
) -> list[tuple[str, float]]:
    """Rank items by cosine similarity to the user vector.

    Args:
        user_vec: the query vector.
        item_vecs: {sku_id: vector}.
        k: optional cap on results (None = return all).

    Returns:
        [(sku_id, similarity)] sorted by similarity desc, then sku_id asc for
        deterministic tie-breaking.
    """
    scored = [
        (sku_id, cosine_similarity(user_vec, vec))
        for sku_id, vec in item_vecs.items()
    ]
    scored.sort(key=lambda t: (-t[1], t[0]))
    return scored if k is None else scored[:k]
