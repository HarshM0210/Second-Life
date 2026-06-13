"""Offline evaluation harness — NDCG@10, Recall@k, MRR.

Pure numpy, zero new deps. Measures retrieval quality on the ESCI subset:
for each query, embed query + products, rank by cosine, compare to graded labels.
"""
from __future__ import annotations

import numpy as np
from typing import Callable

from .esci_loader import load_esci, ESCIQuery


# ---------- Metrics (pure numpy) ----------

def _dcg(relevances: np.ndarray, k: int) -> float:
    """Discounted cumulative gain at k."""
    rel = relevances[:k]
    gains = (2.0 ** rel - 1.0)
    discounts = np.log2(np.arange(len(rel)) + 2)
    return float(np.sum(gains / discounts))


def ndcg_at_k(relevances: np.ndarray, k: int) -> float:
    """Normalized DCG@k. relevances = array of graded scores in ranked order."""
    dcg = _dcg(relevances, k)
    ideal = _dcg(np.sort(relevances)[::-1], k)
    return dcg / ideal if ideal > 0 else 0.0


def recall_at_k(relevances: np.ndarray, k: int, threshold: int = 1) -> float:
    """Fraction of relevant items (relevance >= threshold) in top-k."""
    total_relevant = int(np.sum(relevances >= threshold))
    if total_relevant == 0:
        return 0.0
    hits = int(np.sum(relevances[:k] >= threshold))
    return hits / total_relevant


def mrr(relevances: np.ndarray, threshold: int = 1) -> float:
    """Mean reciprocal rank — 1/(rank of first relevant item)."""
    for i, r in enumerate(relevances):
        if r >= threshold:
            return 1.0 / (i + 1)
    return 0.0


# ---------- Eval harness ----------

def evaluate(
    embed_fn: Callable[[list[str]], list[list[float]]],
    data: list[ESCIQuery] | None = None,
    k: int = 10,
) -> dict[str, float]:
    """Run eval over ESCI subset.

    Args:
        embed_fn: batch embed function (texts -> list of vectors).
        data: ESCI queries (loaded from cache if None).
        k: cutoff for NDCG/Recall.

    Returns:
        {"ndcg@k": float, "recall@k": float, "mrr": float, "num_queries": int}
    """
    if data is None:
        data = load_esci()

    ndcgs, recalls, mrrs = [], [], []

    for query_data in data:
        products = query_data["products"]
        if len(products) < 2:
            continue

        # Embed query and products
        texts = [query_data["query"]] + [p["product_text"] for p in products]
        vecs = embed_fn(texts)
        q_vec = np.array(vecs[0])
        p_vecs = np.array(vecs[1:])

        # Rank by cosine similarity (vectors assumed normalized)
        sims = p_vecs @ q_vec
        ranked_idx = np.argsort(-sims)
        relevances = np.array([products[i]["relevance"] for i in ranked_idx])

        ndcgs.append(ndcg_at_k(relevances, k))
        recalls.append(recall_at_k(relevances, k))
        mrrs.append(mrr(relevances))

    return {
        f"ndcg@{k}": float(np.mean(ndcgs)),
        f"recall@{k}": float(np.mean(recalls)),
        "mrr": float(np.mean(mrrs)),
        "num_queries": len(ndcgs),
    }
