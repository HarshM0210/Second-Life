"""Maddie — Phase 2.1 upgrade tests for U1-U5.

Covers: ESCI loader edges, metric correctness on toy rankings, embedder swap,
Qwen3-Reranker, policy-flip behavior, retrieve() purity preserved.
"""
import json
import math
from pathlib import Path

import numpy as np
import pytest

from recommend.config import EMBED
from recommend.embedder import embed_text, embed_texts
from recommend.esci_loader import load_esci, _synthetic_fallback, LABEL_TO_GRADE
from recommend.eval_harness import ndcg_at_k, recall_at_k, mrr, evaluate
from recommend.pipeline import Recommender
from recommend.policy import MarketState, policy_adjustment, POLICY
from recommend.rerank import rerank
from recommend.retrieve import retrieve
from recommend.schemas import HealthCard, UserContext

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


# ---------- U1: ESCI loader ----------

class TestESCILoader:
    def test_loads_from_cache(self):
        data = load_esci()
        assert len(data) > 0
        assert "query" in data[0] and "products" in data[0]

    def test_query_has_graded_products(self):
        data = load_esci()
        q = data[0]
        assert len(q["products"]) >= 1
        p = q["products"][0]
        assert "product_id" in p and "product_text" in p and "relevance" in p
        assert p["relevance"] in (0, 1, 2, 3)

    def test_synthetic_fallback(self):
        data = _synthetic_fallback()
        assert len(data) == 1
        assert data[0]["query"] == "running shoes"

    def test_label_mapping(self):
        assert LABEL_TO_GRADE["Exact"] == 3
        assert LABEL_TO_GRADE["Irrelevant"] == 0


# ---------- U2: Metric correctness ----------

class TestMetrics:
    def test_perfect_ranking_ndcg_is_one(self):
        # Already sorted by relevance desc
        rels = np.array([3.0, 2.0, 1.0, 0.0])
        assert ndcg_at_k(rels, 4) == pytest.approx(1.0)

    def test_worst_ranking_ndcg_is_low(self):
        rels = np.array([0.0, 0.0, 0.0, 3.0])
        assert ndcg_at_k(rels, 4) < 0.5

    def test_recall_at_k_perfect(self):
        rels = np.array([3.0, 2.0, 1.0, 0.0])
        assert recall_at_k(rels, 4, threshold=1) == 1.0

    def test_recall_at_k_partial(self):
        rels = np.array([0.0, 0.0, 3.0, 2.0])
        assert recall_at_k(rels, 2, threshold=1) == 0.0

    def test_mrr_first_position(self):
        rels = np.array([3.0, 0.0, 0.0])
        assert mrr(rels) == 1.0

    def test_mrr_second_position(self):
        rels = np.array([0.0, 3.0, 0.0])
        assert mrr(rels) == 0.5

    def test_mrr_no_relevant(self):
        rels = np.array([0.0, 0.0, 0.0])
        assert mrr(rels) == 0.0


# ---------- U3: Embedder (gte-modernbert-base) ----------

class TestGTEModernBERT:
    def test_correct_dim(self):
        v = embed_text("test")
        assert len(v) == EMBED.dim == 768

    def test_dense_output(self):
        v = embed_text("running shoes lightweight")
        non_zero = sum(1 for x in v if abs(x) > 1e-6)
        assert non_zero > EMBED.dim * 0.9

    def test_semantic_similarity_relative(self):
        v1 = embed_text("Nike running shoes")
        v2 = embed_text("Adidas running shoes")
        v3 = embed_text("baby monitor camera")
        from recommend.retrieve import cosine_similarity
        sim_same = cosine_similarity(v1, v2)
        sim_diff = cosine_similarity(v1, v3)
        assert sim_same > sim_diff + 0.1


# ---------- U4: Cross-encoder (Qwen3-Reranker) ----------

class TestCrossEncoder:
    def test_relevant_scores_higher(self):
        from recommend.cross_encoder import _get_reranker
        reranker = _get_reranker()
        scores = reranker.predict([
            ("running shoes", "Nike Air Max running shoes lightweight"),
            ("running shoes", "baby monitor video night vision"),
        ])
        assert scores[0] > scores[1]

    def test_pipeline_with_ce_flag(self):
        catalog = json.loads((FIXTURES / "catalog.json").read_text())
        cards_raw = json.loads((FIXTURES / "health_cards.json").read_text())
        sku_text = {i["sku_id"]: i["text"] for i in catalog}
        cards = {c["sku_id"]: HealthCard.from_dict(c) for c in cards_raw}
        rec = Recommender(sku_text, cards, use_cross_encoder=True)
        user = UserContext(user_id="u", searches=["running shoes"])
        feed = rec.recommend(user, k=3)
        assert len(feed.items) == 3
        # Nike should still be top (CE agrees with cosine on obvious cases)
        assert "NIKE" in feed.items[0].sku_id


# ---------- U5: Market-aware policy ----------

class TestPolicy:
    def test_neutral_market_no_adjustment(self):
        adj, reasons = policy_adjustment(MarketState(), is_renewed=True)
        assert adj == 0.0
        assert reasons == []

    def test_new_items_never_adjusted(self):
        glut = MarketState(inventory_level=1.0)
        adj, reasons = policy_adjustment(glut, is_renewed=False)
        assert adj == 0.0

    def test_inventory_glut_boosts_renewed(self):
        glut = MarketState(inventory_level=0.95)
        adj, reasons = policy_adjustment(glut, is_renewed=True)
        assert adj > 0
        assert any("inventory" in r for r in reasons)

    def test_high_demand_dampens(self):
        hot = MarketState(demand_intensity=0.9)
        adj, reasons = policy_adjustment(hot, is_renewed=True)
        assert adj < 0
        assert any("demand" in r for r in reasons)

    def test_high_logistics_penalizes(self):
        expensive = MarketState(logistics_cost=0.9)
        adj, reasons = policy_adjustment(expensive, is_renewed=True)
        assert adj < 0
        assert any("logistics" in r for r in reasons)

    def test_policy_flip_changes_ranking(self):
        """The demo moment: toggling market state visibly changes scores."""
        retrieved = [("ren", 0.8), ("new", 0.8)]
        cards = {
            "ren": HealthCard("ren", is_renewed=True, health_score=94,
                            confidence=0.9, price=70, original_price=100),
            "new": HealthCard("new", is_renewed=False),
        }
        # Normal
        feed_normal = rerank("u", retrieved, cards, market_state=MarketState())
        # Glut
        feed_glut = rerank("u", retrieved, cards,
                          market_state=MarketState(inventory_level=0.95))
        ren_normal = next(i for i in feed_normal.items if i.sku_id == "ren")
        ren_glut = next(i for i in feed_glut.items if i.sku_id == "ren")
        assert ren_glut.score > ren_normal.score

    def test_retrieve_purity_preserved(self):
        """retrieve() still works standalone — Module 5 contract intact."""
        user = [1.0, 0.0, 0.0]
        items = {"a": [1.0, 0.0, 0.0], "b": [0.0, 1.0, 0.0]}
        result = retrieve(user, items)
        assert result[0] == ("a", pytest.approx(1.0))
        assert result[1][0] == "b"
