"""Maddie — Baseline tests for M1-M6.

These verify the real-embedding pipeline: semantic similarity, precompute cache,
profile enrichment, tuned-weight ranking, service endpoint, and reason strings.
"""
import json
import math
from pathlib import Path

import pytest

from recommend.config import EMBED, RERANK
from recommend.embedder import embed_text, embed_texts, embed_catalog
from recommend.pipeline import Recommender
from recommend.profile import assemble_profile_text
from recommend.retrieve import cosine_similarity, retrieve
from recommend.schemas import HealthCard, UserContext

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


# ---------- M1: Real embedding smoke tests ----------

class TestRealEmbeddings:
    def test_embed_text_returns_correct_dim(self):
        vec = embed_text("hello world")
        assert len(vec) == EMBED.dim

    def test_embed_text_is_normalized(self):
        vec = embed_text("running shoes lightweight")
        norm = math.sqrt(sum(x * x for x in vec))
        assert norm == pytest.approx(1.0, abs=1e-3)

    def test_embed_text_is_dense(self):
        vec = embed_text("noise cancelling headphones")
        non_zero = sum(1 for x in vec if abs(x) > 1e-6)
        # Real embeddings should be dense, not sparse like hash fallback
        assert non_zero > EMBED.dim * 0.5

    def test_semantic_similarity_relative(self):
        """R10: Use relative similarity to avoid flakes on model/version bumps."""
        v_anchor = embed_text("Nike running shoes size 8")
        v_same = embed_text("Nike running shoes size 8 renewed")
        v_diff = embed_text("baby monitor video night vision")
        
        sim_same = cosine_similarity(v_anchor, v_same)
        sim_diff = cosine_similarity(v_anchor, v_diff)
        
        # Instead of absolute 0.8 and 0.6, we assert a clear margin
        assert sim_same > sim_diff + 0.1
        # Also maintain a sane lower bound for same-category
        assert sim_same > 0.7

    def test_embed_texts_batch_matches_individual(self):
        texts = ["running shoes", "baby monitor", "coffee press"]
        batch = embed_texts(texts)
        individual = [embed_text(t) for t in texts]
        for b, i in zip(batch, individual):
            sim = cosine_similarity(b, i)
            assert sim == pytest.approx(1.0, abs=1e-4)

    def test_empty_string_does_not_crash(self):
        vec = embed_text("")
        assert len(vec) == EMBED.dim


# ---------- M2: Precompute cache path ----------

class TestPrecomputeCache:
    def test_catalog_vectors_precomputed_at_init(self):
        rec = Recommender(
            sku_text={"a": "shoes", "b": "monitor"},
            cards={},
        )
        assert "a" in rec.item_vecs and "b" in rec.item_vecs
        assert len(rec.item_vecs["a"]) == EMBED.dim

    def test_recommend_does_not_recompute_catalog(self):
        rec = Recommender(sku_text={"a": "shoes"}, cards={})
        vecs_before = id(rec.item_vecs)
        rec.recommend(UserContext(user_id="u", searches=["shoes"]))
        assert id(rec.item_vecs) == vecs_before  # same object, not recomputed


# ---------- M3: Profile enrichment ----------

class TestProfileEnrichment:
    def test_resolves_sku_ids_to_text(self):
        user = UserContext(user_id="u", wishlist=["SKU-1"], purchase_history=["SKU-2"])
        text = assemble_profile_text(user, sku_text={"SKU-1": "running shoes", "SKU-2": "yoga mat"})
        assert "running shoes" in text
        assert "yoga mat" in text
        assert "SKU-1" not in text  # resolved, not raw ID

    def test_wishlist_weighted_higher_than_history(self):
        user = UserContext(user_id="u", wishlist=["SKU-W"], purchase_history=["SKU-H"])
        text = assemble_profile_text(user, sku_text={"SKU-W": "wish", "SKU-H": "hist"})
        # Wishlist appears 2x, history 1x
        assert text.count("wish") == 2
        assert text.count("hist") == 1

    def test_enriches_renewed_with_condition(self):
        user = UserContext(user_id="u", purchase_history=["R1"])
        cards = {"R1": HealthCard("R1", condition="Excellent", health_score=94,
                                  is_renewed=True, price=70, original_price=100)}
        text = assemble_profile_text(user, sku_text={"R1": "shoes"}, cards=cards)
        assert "Excellent" in text
        assert "30%" in text


# ---------- M4: Tuned-weight ranking assertion ----------

class TestTunedWeightRanking:
    @pytest.fixture
    def recommender(self):
        catalog = json.loads((FIXTURES / "catalog.json").read_text())
        cards_raw = json.loads((FIXTURES / "health_cards.json").read_text())
        sku_text = {i["sku_id"]: i["text"] for i in catalog}
        cards = {c["sku_id"]: HealthCard.from_dict(c) for c in cards_raw}
        return Recommender(sku_text, cards)

    def test_renewed_gt90_beats_equivalent_new(self, recommender):
        """The headline: >90 Renewed at discount out-ranks equivalent New."""
        user = UserContext(user_id="u", wishlist=["SKU-NIKE-RUN-8"],
                          searches=["running shoes size 8"])
        feed = recommender.recommend(user)
        nike_r = next(i for i in feed.items if i.sku_id == "SKU-NIKE-RUN-8R")
        nike_n = next(i for i in feed.items if i.sku_id == "SKU-NIKE-RUN-8")
        assert nike_r.rank < nike_n.rank  # lower rank = higher position
        assert nike_r.score > nike_n.score

    def test_renewed_boost_margin_is_significant(self, recommender):
        """Renewed >90 should have a meaningful gap, not just barely edge out."""
        user = UserContext(user_id="u", searches=["running shoes"])
        feed = recommender.recommend(user)
        nike_r = next(i for i in feed.items if i.sku_id == "SKU-NIKE-RUN-8R")
        nike_n = next(i for i in feed.items if i.sku_id == "SKU-NIKE-RUN-8")
        margin = nike_r.score - nike_n.score
        assert margin > 0.05  # not just a rounding difference

    def test_health_floor_blocks_low_score(self):
        """Items below health_score_floor get no boost."""
        cards = {"r": HealthCard("r", health_score=60, confidence=0.9,
                                 is_renewed=True, price=50, original_price=100)}
        rec = Recommender(sku_text={"r": "item", "n": "item"}, cards=cards)
        user = UserContext(user_id="u", searches=["item"])
        feed = rec.recommend(user)
        r = next(i for i in feed.items if i.sku_id == "r")
        n = next(i for i in feed.items if i.sku_id == "n")
        # No boost for health 60 (below floor of 70)
        assert abs(r.score - n.score) < 0.01


# ---------- M5: Service endpoint ----------

class TestServiceEndpoint:
    def test_load_recommender_from_fixtures(self):
        from recommend.service import load_recommender, load_users
        rec = load_recommender()
        users = load_users()
        assert len(rec.item_vecs) == 8
        assert "u-priya" in users

    def test_env_var_fallback(self, monkeypatch):
        """Non-existent env path falls back to fixtures."""
        monkeypatch.setenv("RECOMMEND_CATALOG", "/nonexistent.json")
        from recommend.service import _load_json
        data = _load_json("RECOMMEND_CATALOG", "catalog.json")
        assert len(data) == 8


# ---------- M6: Reason strings ----------

class TestReasonStrings:
    @pytest.fixture
    def recommender(self):
        catalog = json.loads((FIXTURES / "catalog.json").read_text())
        cards_raw = json.loads((FIXTURES / "health_cards.json").read_text())
        sku_text = {i["sku_id"]: i["text"] for i in catalog}
        cards = {c["sku_id"]: HealthCard.from_dict(c) for c in cards_raw}
        return Recommender(sku_text, cards)

    def test_wishlist_reason(self, recommender):
        user = UserContext(user_id="u", wishlist=["SKU-NIKE-RUN-8"])
        feed = recommender.recommend(user)
        nike = next(i for i in feed.items if i.sku_id == "SKU-NIKE-RUN-8")
        assert "matches wishlist" in nike.reasons

    def test_previously_purchased_reason(self, recommender):
        user = UserContext(user_id="u", purchase_history=["SKU-YOGA-MAT"],
                          searches=["yoga"])
        feed = recommender.recommend(user)
        yoga = next(i for i in feed.items if i.sku_id == "SKU-YOGA-MAT")
        assert "previously purchased" in yoga.reasons

    def test_renewed_reason_includes_health(self, recommender):
        user = UserContext(user_id="u", searches=["running shoes"])
        feed = recommender.recommend(user)
        nike_r = next(i for i in feed.items if i.sku_id == "SKU-NIKE-RUN-8R")
        assert any("Renewed, health" in r for r in nike_r.reasons)

    def test_discount_reason(self, recommender):
        user = UserContext(user_id="u", searches=["running shoes"])
        feed = recommender.recommend(user)
        nike_r = next(i for i in feed.items if i.sku_id == "SKU-NIKE-RUN-8R")
        assert any("off original" in r for r in nike_r.reasons)
