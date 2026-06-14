"""Baseline test suite for Module 5 P2P Exchange.

All tests mock CLIP (via conftest autouse fixture) so no model download is needed.
Run: pytest tests/test_baseline.py -v
"""
import pytest
from unittest.mock import patch, MagicMock

from p2p.schemas import HealthCard, ItemListing, FeatureVector, PriceQuote, PickupJob
from p2p.config import CONFIG


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

LISTING_FULL = {
    "sku_id": "SKU-001",
    "category": "electronics",
    "original_price": 5000,
    "age_months": 6,
    "brand_tier": "premium",
    "has_box": True,
    "accessories_complete": True,
    "media_refs": ["img1.jpg"],
}

LISTING_WITH_CARD = {
    **LISTING_FULL,
    "health_card": {
        "sku_id": "SKU-001",
        "condition": "Excellent",
        "health_score": 88,
        "confidence": 0.91,
        "price": 2100,
        "original_price": 5000,
        "is_renewed": True,
    },
}

QUOTE_REQUIRED_KEYS = {
    "sku_id", "gross_price", "low", "high", "confidence",
    "fee", "net_payout", "currency", "feature_source", "reasons",
}

JOB_REQUIRED_KEYS = {"job_id", "sku_id", "status", "pickup_eta", "agent", "created_at"}


# ===========================================================================
# 1. CONTRACT CONFORMANCE
# ===========================================================================

class TestContractConformance:
    def test_item_listing_tolerates_extra_fields(self):
        d = {**LISTING_FULL, "extra_field": "ignored", "unknown": 123}
        listing = ItemListing.from_dict(d)
        assert listing.sku_id == "SKU-001"
        assert listing.category == "electronics"

    def test_item_listing_tolerates_missing_fields(self):
        listing = ItemListing.from_dict({"sku_id": "X"})
        assert listing.sku_id == "X"
        assert listing.category == "general"
        assert listing.original_price == 0.0

    def test_item_listing_from_empty_dict(self):
        listing = ItemListing.from_dict({})
        assert listing.sku_id == ""

    def test_health_card_tolerates_extra_fields(self):
        d = {"sku_id": "S1", "health_score": 80, "bonus": True}
        hc = HealthCard.from_dict(d)
        assert hc.health_score == 80.0
        assert hc.sku_id == "S1"

    def test_health_card_tolerates_missing_fields(self):
        hc = HealthCard.from_dict({"sku_id": "S1"})
        assert hc.health_score == 0.0
        assert hc.condition == "Unknown"

    def test_health_card_from_none(self):
        hc = HealthCard.from_dict(None)
        assert hc.sku_id == ""

    def test_price_quote_to_dict_has_all_keys(self):
        pq = PriceQuote(sku_id="X", gross_price=1000, low=900, high=1100,
                        confidence=0.85, fee=120, net_payout=880,
                        feature_source="direct", reasons=["test"])
        d = pq.to_dict()
        assert QUOTE_REQUIRED_KEYS.issubset(d.keys())

    def test_pickup_job_to_dict_has_all_keys(self):
        job = PickupJob(job_id="j1", sku_id="s1", status="scheduled",
                        pickup_eta="2-4 hours", agent="courier-100",
                        created_at="2026-01-01T00:00:00")
        d = job.to_dict()
        assert JOB_REQUIRED_KEYS.issubset(d.keys())


# ===========================================================================
# 2. DUAL-PATH FEATURE EXTRACTION
# ===========================================================================

class TestDualPath:
    def test_health_card_path(self):
        from p2p.features import extract_features
        listing = ItemListing.from_dict(LISTING_WITH_CARD)
        fv = extract_features(listing)
        assert fv.source == "health_card"
        assert fv.condition_score == 88.0

    def test_direct_path_no_card(self):
        from p2p.features import extract_features
        listing = ItemListing.from_dict(LISTING_FULL)
        fv = extract_features(listing)
        assert fv.source == "direct"
        assert fv.condition_score == 75.0  # mocked CLIP returns 75.0

    def test_direct_path_when_health_score_zero(self):
        from p2p.features import extract_features
        d = {**LISTING_FULL, "health_card": {"sku_id": "X", "health_score": 0}}
        listing = ItemListing.from_dict(d)
        fv = extract_features(listing)
        assert fv.source == "direct"

    def test_clip_unavailable_graceful_fallback(self):
        """When CLIP returns 50.0 (its own fallback), features still work."""
        from p2p.features import extract_features
        with patch("p2p.media.score_condition", return_value=50.0):
            listing = ItemListing.from_dict(LISTING_FULL)
            fv = extract_features(listing)
            assert fv.source == "direct"
            assert fv.condition_score == 50.0


# ===========================================================================
# 2b. MEDIA PATH RESOLUTION (P10 — CLIP must actually receive images)
# ===========================================================================

class TestMediaResolution:
    """Regression for the silent-constant bug: fixture media_refs were unresolvable,
    so the Direct path always fell back to 50.0 without CLIP ever seeing an image."""

    def test_fixture_refs_resolve_to_real_images(self):
        """The shipped fixtures must point at images that actually load."""
        import json
        from pathlib import Path
        from p2p import media
        listings = json.loads(
            (Path(__file__).resolve().parent.parent / "fixtures" / "listings.json").read_text()
        )
        refs = [r for item in listings for r in item.get("media_refs", [])]
        assert refs, "fixtures should reference media"
        imgs = media._load_images(refs)
        assert len(imgs) == len(refs), "every fixture media_ref must resolve to a loadable image"

    def test_missing_ref_loads_nothing(self):
        from p2p import media
        assert media._load_images(["fixtures/media/does_not_exist.jpg"]) == []

    @pytest.mark.real_clip
    def test_real_image_produces_non_fallback_score(self):
        """With the real model, a present image yields a CLIP score (not the 50.0
        constant), and an absent image still returns the fallback."""
        pytest.importorskip("torch")
        pytest.importorskip("sentence_transformers")
        from pathlib import Path
        from p2p import media
        media._model = None  # force a fresh load attempt
        img = str(Path(__file__).resolve().parent.parent / "fixtures" / "media" / "elec_001_front.jpg")
        score = media.score_condition([img])
        if not media.is_model_loaded():
            pytest.skip("CLIP model could not be loaded (offline / not downloaded)")
        assert 0.0 <= score <= 100.0
        assert score != media._FALLBACK, "real CLIP scoring must not return the constant fallback"
        assert media.score_condition(["fixtures/media/nope.jpg"]) == media._FALLBACK


# ===========================================================================
# 3. PRICING MONOTONICITY
# ===========================================================================

class TestPricingMonotonicity:
    """Use heuristic path directly for deterministic monotonicity checks."""

    def _heuristic(self, **kwargs):
        from p2p.pricing import _heuristic_quote
        defaults = dict(condition_score=70, original_price=5000, age_months=12,
                        category_demand=0.8, category_depreciation=0.1,
                        brand_multiplier=1.0, completeness=1.0, source="direct")
        defaults.update(kwargs)
        fv = FeatureVector(**defaults)
        return _heuristic_quote(fv)

    def test_better_condition_higher_price(self):
        q_low = self._heuristic(condition_score=40)
        q_high = self._heuristic(condition_score=90)
        assert q_high.gross_price > q_low.gross_price

    def test_older_age_lower_price(self):
        q_young = self._heuristic(age_months=3)
        q_old = self._heuristic(age_months=48)
        assert q_young.gross_price > q_old.gross_price

    def test_higher_original_price_higher_quote(self):
        q_cheap = self._heuristic(original_price=1000)
        q_expensive = self._heuristic(original_price=10000)
        assert q_expensive.gross_price > q_cheap.gross_price

    def test_higher_demand_higher_price(self):
        q_low_demand = self._heuristic(category_demand=0.4)
        q_high_demand = self._heuristic(category_demand=0.95)
        assert q_high_demand.gross_price > q_low_demand.gross_price

    def test_low_lte_point_lte_high(self):
        q = self._heuristic()
        assert q.low <= q.gross_price <= q.high


# ===========================================================================
# 4. DETERMINISM
# ===========================================================================

class TestDeterminism:
    def test_synthetic_data_deterministic(self):
        from p2p.synth import generate
        d1 = generate(n=100, seed=99)
        d2 = generate(n=100, seed=99)
        assert d1 == d2

    def test_train_deterministic_predictions(self):
        """Train twice with same seed → identical predictions."""
        import tempfile, os, joblib
        import pandas as pd
        from p2p.synth import generate
        from sklearn.ensemble import GradientBoostingRegressor
        from sklearn.model_selection import train_test_split

        data = pd.DataFrame(generate(n=500, seed=7))
        feats = ["condition_score", "original_price", "age_months",
                 "category_demand", "category_depreciation", "brand_multiplier", "completeness"]
        X, y = data[feats], data["true_price"]

        def _train(seed):
            m = GradientBoostingRegressor(loss="quantile", alpha=0.5,
                                          n_estimators=50, max_depth=3, random_state=seed)
            m.fit(X, y)
            return m.predict(X[:5])

        p1 = _train(7)
        p2 = _train(7)
        assert list(p1) == list(p2)


# ===========================================================================
# 5. PAYOUT MATH
# ===========================================================================

class TestPayoutMath:
    def test_net_equals_gross_minus_fee(self):
        from p2p.pricing import _heuristic_quote
        fv = FeatureVector(condition_score=80, original_price=5000, age_months=6,
                           category_demand=0.8, category_depreciation=0.1,
                           brand_multiplier=1.0, completeness=1.0, source="direct")
        q = _heuristic_quote(fv)
        # Implementation computes fee and net from unrounded point, then rounds
        # gross_price separately, so allow ±1 tolerance
        assert abs(q.net_payout - (q.gross_price - q.fee)) <= 1

    def test_fee_is_12_percent(self):
        from p2p.pricing import _heuristic_quote
        fv = FeatureVector(condition_score=80, original_price=5000, age_months=6,
                           category_demand=0.8, category_depreciation=0.1,
                           brand_multiplier=1.0, completeness=1.0, source="direct")
        q = _heuristic_quote(fv)
        # fee = round(point * 0.12) where point is the unrounded float
        # gross_price = round(point), so fee ≈ round(gross_price * 0.12) within ±1
        assert abs(q.fee - round(q.gross_price * 0.12)) <= 1

    def test_payout_math_various_prices(self):
        from p2p.pricing import _build_quote
        for price in [100, 500, 1234, 9999]:
            fv = FeatureVector(original_price=price * 2, condition_score=80,
                               source="direct")
            q = _build_quote(fv, float(price), price * 0.8, price * 1.2)
            # When point is an exact int float, rounding is exact
            assert q.fee == round(q.gross_price * CONFIG.fee_rate)
            assert q.net_payout == q.gross_price - q.fee


# ===========================================================================
# 6. FALLBACK (model missing / sklearn unavailable)
# ===========================================================================

class TestFallback:
    def test_heuristic_when_model_missing(self):
        """pricing.quote falls back to heuristic when ensure_model raises."""
        from p2p import pricing
        fv = FeatureVector(condition_score=70, original_price=3000, age_months=10,
                           category_demand=0.7, category_depreciation=0.1,
                           brand_multiplier=1.0, completeness=0.8, source="direct")
        with patch.object(pricing, "ensure_model", side_effect=FileNotFoundError("no model")):
            q = pricing.quote(fv)
            assert q.gross_price > 0
            # net ≈ gross - fee (rounding tolerance of 1 from float→int)
            assert abs(q.net_payout - (q.gross_price - q.fee)) <= 1
            assert q.feature_source == "direct"

    def test_heuristic_never_crashes(self):
        """Even with extreme inputs, heuristic produces a valid quote."""
        from p2p.pricing import _heuristic_quote
        for cs in [0, 1, 100]:
            for op in [0, 1, 99999]:
                q = _heuristic_quote(FeatureVector(
                    condition_score=cs, original_price=op, age_months=72,
                    category_demand=0.3, category_depreciation=0.25,
                    brand_multiplier=0.85, completeness=0.0, source="direct"))
                assert q.low <= q.gross_price <= q.high
                assert q.net_payout == q.gross_price - q.fee


# ===========================================================================
# 7. PICKUP
# ===========================================================================

class TestPickup:
    def test_schedule_creates_job(self):
        from p2p import pickup
        job = pickup.schedule("SKU-TEST-1")
        assert job.status == "scheduled"
        assert job.sku_id == "SKU-TEST-1"
        assert job.job_id  # non-empty
        assert job.pickup_eta
        assert job.agent.startswith("courier-")

    def test_get_job_returns_scheduled(self):
        from p2p import pickup
        job = pickup.schedule("SKU-TEST-2")
        retrieved = pickup.get_job(job.job_id)
        assert retrieved is not None
        assert retrieved.job_id == job.job_id
        assert retrieved.status == "scheduled"

    def test_unknown_job_id_returns_none(self):
        from p2p import pickup
        assert pickup.get_job("nonexistent-id-xyz") is None


# ===========================================================================
# 8. SERVICE ENDPOINTS
# ===========================================================================

class TestServiceEndpoints:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from p2p.service import app
        with TestClient(app) as c:
            yield c

    def test_post_quote_returns_valid_shape(self, client):
        with patch("p2p.pricing.ensure_model", side_effect=FileNotFoundError):
            resp = client.post("/quote", json=LISTING_FULL)
        assert resp.status_code == 200
        body = resp.json()
        assert QUOTE_REQUIRED_KEYS.issubset(body.keys())
        assert body["feature_source"] in ("direct", "health_card")
        assert body["low"] <= body["gross_price"] <= body["high"]

    def test_post_quote_with_health_card(self, client):
        with patch("p2p.pricing.ensure_model", side_effect=FileNotFoundError):
            resp = client.post("/quote", json=LISTING_WITH_CARD)
        assert resp.status_code == 200
        assert resp.json()["feature_source"] == "health_card"

    def test_post_accept_returns_job(self, client):
        resp = client.post("/accept", json={"sku_id": "SKU-SVC-1"})
        assert resp.status_code == 200
        body = resp.json()
        assert JOB_REQUIRED_KEYS.issubset(body.keys())
        assert body["status"] == "scheduled"

    def test_get_pickup_found(self, client):
        resp = client.post("/accept", json={"sku_id": "SKU-SVC-2"})
        job_id = resp.json()["job_id"]
        resp2 = client.get(f"/pickup/{job_id}")
        assert resp2.status_code == 200
        assert resp2.json()["job_id"] == job_id

    def test_get_pickup_not_found(self, client):
        resp = client.get("/pickup/does-not-exist")
        assert resp.status_code == 404

    def test_health_endpoint(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert "model_loaded" in body
        assert "clip_loaded" in body

    def test_health_reports_model_loaded_after_warmup(self, client):
        """P11: lifespan warms the pricing model, so /health must not claim it's
        unloaded once the service is up (the flag must reflect real state)."""
        from p2p import pricing
        assert pricing._models, "lifespan should have warmed the pricing model"
        body = client.get("/health").json()
        assert body["model_loaded"] is True

    def test_health_clip_flag_matches_real_state(self, client):
        """clip_loaded must mirror media's actual lazy-load state, not a guess."""
        from p2p import media
        body = client.get("/health").json()
        assert body["clip_loaded"] == media.is_model_loaded()


# ===========================================================================
# 9. PHASE B — neural quantile-MLP + eval (post-2023 model upgrade)
# ===========================================================================

class TestEvalMetrics:
    def test_metric_correctness_perfect(self):
        from p2p import eval as ev
        import numpy as np
        y = np.array([10., 20., 30., 40.])
        assert ev.mae(y, y) == 0.0
        assert ev.r2(y, y) == 1.0
        assert ev.rmsle(y, y) < 1e-9
        assert ev.interval_coverage(y, y - 1, y + 1) == 1.0
        assert ev.interval_coverage(y, y + 1, y + 2) == 0.0

    def test_mae_value(self):
        from p2p import eval as ev
        assert ev.mae([0, 0], [1, 3]) == 2.0


class TestQuantileMLP:
    def test_quantiles_ordered_and_positive(self):
        pytest.importorskip("torch")
        from p2p.synth import generate_xy
        from p2p.model import PriceModel
        X, y = generate_xy(n=1500, seed=1)
        m = PriceModel().fit(X[:1200], y[:1200], epochs=20, seed=1)
        q10, q50, q90 = m.predict(X[1200:])
        assert (q10 <= q50 + 1e-6).all()
        assert (q50 <= q90 + 1e-6).all()
        assert (q50 > 0).all()
        assert m.cal_scale > 0

    def test_save_load_roundtrip(self, tmp_path):
        pytest.importorskip("torch")
        import numpy as np
        from p2p.synth import generate_xy
        from p2p.model import PriceModel
        X, y = generate_xy(n=900, seed=2)
        m = PriceModel().fit(X, y, epochs=10, seed=2)
        p = tmp_path / "m.pt"
        m.save(str(p))
        m2 = PriceModel.load(str(p))
        a, b = m.predict(X[:5]), m2.predict(X[:5])
        for x, z in zip(a, b):
            np.testing.assert_allclose(x, z, rtol=1e-5, atol=1e-3)


class TestPricingModelLabel:
    def test_quote_uses_mlp_when_available(self):
        """The trained MLP is the live path and the quote says so."""
        from p2p import pricing
        fv = FeatureVector(condition_score=80, original_price=5000, age_months=6,
                           category_demand=0.8, category_depreciation=0.1,
                           brand_multiplier=1.0, completeness=1.0, source="direct")
        q = pricing.quote(fv)
        assert q.model == "neural-quantile-mlp"
        assert q.low <= q.gross_price <= q.high

    def test_fallback_is_labeled_not_silent(self):
        """If the MLP can't load, the fallback is a heuristic that SAYS it's a fallback."""
        from p2p import pricing
        fv = FeatureVector(condition_score=80, original_price=5000, source="direct")
        with patch.object(pricing, "ensure_model", side_effect=RuntimeError("no torch")):
            q = pricing.quote(fv)
        assert q.model == "heuristic-fallback"
        assert q.gross_price > 0


def test_mlp_beats_or_matches_baseline():
    """Slide-number run: full train + eval vs the synthetic-GBM baseline.
    Heavy (~1 min) — self-skips unless P2P_RUN_EVAL=1."""
    import os
    if os.environ.get("P2P_RUN_EVAL") != "1":
        pytest.skip("set P2P_RUN_EVAL=1 to run the full eval")
    from p2p import eval as ev
    res = ev.evaluate_models()
    assert res["mlp"]["r2"] >= res["baseline_gbm"]["r2"] - 0.02
    assert 0.7 <= res["mlp"]["coverage"] <= 0.9
