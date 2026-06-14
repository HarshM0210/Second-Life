"""Offline evaluation harness — NDCG@10, Recall@k, MRR.

Pure numpy for the metrics. Measures ranking quality on the ESCI subset:
for each query, rank its candidate products by cosine (optionally cross-encoder
reranked), compare to graded labels.

**Negative pooling (the methodology fix):** the raw ESCI subset has only ~2.7
candidates/query — far too few to differentiate rankers (NDCG@10 over ~3 items is
near-trivial). We pool `num_negatives` distractor products sampled from *other*
queries (relevance 0) into each candidate set, so there are enough items to
actually measure ranking. Seeded for determinism.
"""
from __future__ import annotations

import random
import numpy as np
from typing import Callable, Optional

from .esci_loader import load_esci, ESCIQuery

RerankFn = Callable[[str, list[tuple[str, float]], dict[str, str], int], list[tuple[str, float]]]


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
    num_negatives: int = 50,
    seed: int = 42,
    reranker_fn: Optional[RerankFn] = None,
    rerank_top_n: int = 20,
    max_queries: int | None = None,
) -> dict[str, float]:
    """Run eval over the ESCI subset with negative pooling.

    Args:
        embed_fn: batch embed function (texts -> list of vectors, assumed L2-normalized).
        data: ESCI queries (loaded from cache if None).
        k: cutoff for NDCG/Recall.
        num_negatives: distractor products (relevance 0) pooled into each query's
            candidate set from other queries. 0 = raw ESCI (the old, too-thin setup).
        seed: RNG seed for negative sampling (determinism).
        reranker_fn: optional cross-encoder rerank `(query, [(id, sim)], texts, top_n)`
            applied to the cosine ranking before scoring. None = embedding-only.
        rerank_top_n: how many top candidates the reranker re-scores.
        max_queries: cap evaluated queries (useful to bound cross-encoder cost).

    Returns:
        {"ndcg@k", "recall@k", "mrr", "num_queries", "avg_candidates"}.
    """
    if data is None:
        data = load_esci()

    queries = [q for q in data if len(q["products"]) >= 2]
    if max_queries is not None:
        queries = queries[:max_queries]

    # Global product pool (dedup) for negative sampling + one batched embed pass.
    pool: dict[str, str] = {}
    for q in data:
        for p in q["products"]:
            pool.setdefault(p["product_id"], p["product_text"])
    pool_ids = list(pool.keys())

    # Precompute all product + query vectors once (avoids re-embedding per query).
    prod_vecs = embed_fn([pool[i] for i in pool_ids])
    vec_by_id = {i: np.array(v) for i, v in zip(pool_ids, prod_vecs)}
    q_vecs = embed_fn([q["query"] for q in queries])

    rng = random.Random(seed)
    ndcgs, recalls, mrrs, cand_counts = [], [], [], []

    for qi, q in enumerate(queries):
        rel_by_id = {p["product_id"]: p["relevance"] for p in q["products"]}
        own_ids = set(rel_by_id)

        negs = []
        if num_negatives > 0:
            choices = [pid for pid in pool_ids if pid not in own_ids]
            negs = rng.sample(choices, min(num_negatives, len(choices)))
        cand_ids = list(own_ids) + negs
        cand_counts.append(len(cand_ids))

        qv = q_vecs[qi]
        sims = {pid: float(np.asarray(vec_by_id[pid]) @ np.asarray(qv)) for pid in cand_ids}
        ranked = sorted(cand_ids, key=lambda pid: (-sims[pid], pid))

        if reranker_fn is not None:
            reranked = reranker_fn(
                q["query"], [(pid, sims[pid]) for pid in ranked], pool, rerank_top_n
            )
            ranked = [pid for pid, _ in reranked]

        relevances = np.array([rel_by_id.get(pid, 0) for pid in ranked])
        ndcgs.append(ndcg_at_k(relevances, k))
        recalls.append(recall_at_k(relevances, k))
        mrrs.append(mrr(relevances))

    return {
        f"ndcg@{k}": float(np.mean(ndcgs)),
        f"recall@{k}": float(np.mean(recalls)),
        "mrr": float(np.mean(mrrs)),
        "num_queries": len(ndcgs),
        "avg_candidates": float(np.mean(cand_counts)) if cand_counts else 0.0,
    }
