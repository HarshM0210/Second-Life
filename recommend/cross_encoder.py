"""Two-stage cross-encoder reranker using Qwen3-Reranker-0.6B.

Slots AFTER retrieve() and BEFORE the business-rule rerank(). retrieve() stays
pure (Module 5 contract untouched). This module re-scores the top-N candidates
with a cross-encoder for higher-quality ranking.
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

_reranker = None


def _get_reranker():
    """Lazy-load the cross-encoder model."""
    global _reranker
    if _reranker is None:
        from sentence_transformers import CrossEncoder
        _reranker = CrossEncoder("Qwen/Qwen3-Reranker-0.6B", trust_remote_code=True)
    return _reranker


def cross_encoder_rerank(
    query: str,
    candidates: list[tuple[str, float]],
    texts: dict[str, str],
    top_n: int = 20,
) -> list[tuple[str, float]]:
    """Re-score top-N candidates with the cross-encoder.

    Args:
        query: the user query/profile text.
        candidates: [(sku_id, cosine_sim)] from retrieve(), sorted by sim desc.
        texts: {sku_id: product_text} for cross-encoder input.
        top_n: how many candidates to re-score (rest keep original order below).

    Returns:
        [(sku_id, cross_encoder_score)] re-sorted by CE score, with remaining
        candidates appended at the end (original sim scores normalized to [0,1]).
    """
    to_rescore = candidates[:top_n]
    tail = candidates[top_n:]

    if not to_rescore:
        return candidates

    try:
        reranker = _get_reranker()
        pairs = [(query, texts.get(sku_id, sku_id)) for sku_id, _ in to_rescore]
        scores = reranker.predict(pairs)

        # Normalize CE scores to [0,1] range via sigmoid
        import numpy as np
        norm_scores = 1.0 / (1.0 + np.exp(-np.array(scores)))

        reranked = sorted(
            zip([s for s, _ in to_rescore], norm_scores),
            key=lambda x: -x[1],
        )
        result = [(sku_id, float(score)) for sku_id, score in reranked]

        # Append tail with their original scores scaled to [0, min_reranked)
        if tail and result:
            min_score = result[-1][1] * 0.9
            for i, (sku_id, sim) in enumerate(tail):
                result.append((sku_id, min_score * (1 - i * 0.01)))

        return result
    except Exception as e:
        logger.warning(f"Cross-encoder rerank failed ({e}), using original order")
        return candidates
