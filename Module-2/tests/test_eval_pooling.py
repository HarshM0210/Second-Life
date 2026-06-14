"""Gary (review) — lock the negative-pooling eval fix.

The raw ESCI subset had ~2.7 candidates/query — too thin for NDCG to differentiate
rankers. evaluate() now pools distractor negatives so candidate sets are large
enough to measure ranking. Uses a dummy embed_fn so no model is needed.
"""
import numpy as np

from recommend.eval_harness import evaluate

_DATA = [
    {"query_id": 0, "query": "running shoes",
     "products": [{"product_id": "p1", "product_text": "nike shoes", "relevance": 3},
                  {"product_id": "p2", "product_text": "old sock", "relevance": 0}]},
    {"query_id": 1, "query": "baby monitor",
     "products": [{"product_id": "p3", "product_text": "video monitor", "relevance": 2},
                  {"product_id": "p4", "product_text": "random thing", "relevance": 0}]},
    {"query_id": 2, "query": "coffee press",
     "products": [{"product_id": "p5", "product_text": "french press", "relevance": 3},
                  {"product_id": "p6", "product_text": "junk", "relevance": 0}]},
]


def _dummy_embed(texts):
    """Deterministic 4-dim one-hot embed — no model needed."""
    out = []
    for t in texts:
        v = np.zeros(4)
        v[sum(map(ord, t)) % 4] = 1.0
        out.append(v.tolist())
    return out


def test_pooling_increases_candidate_count():
    r0 = evaluate(_dummy_embed, _DATA, k=10, num_negatives=0)
    r3 = evaluate(_dummy_embed, _DATA, k=10, num_negatives=3)
    assert r0["avg_candidates"] == 2.0           # raw: each query has its 2 products
    assert r3["avg_candidates"] > r0["avg_candidates"]  # pooling adds distractors


def test_pooling_is_deterministic_under_seed():
    a = evaluate(_dummy_embed, _DATA, k=10, num_negatives=3, seed=7)
    b = evaluate(_dummy_embed, _DATA, k=10, num_negatives=3, seed=7)
    assert a == b


def test_metrics_in_valid_range():
    r = evaluate(_dummy_embed, _DATA, k=10, num_negatives=3)
    for key in ("ndcg@10", "recall@10", "mrr"):
        assert 0.0 <= r[key] <= 1.0
    assert r["num_queries"] == 3
