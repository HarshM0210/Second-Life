"""
Unit tests for return_prevention/core/scorer.py

Tests cover:
- Known feature vector with high return-risk inputs → probability > 0.5
- Known feature vector with low return-risk inputs → probability < 0.5
- Output always in [0.0, 1.0] for 10 varied hand-crafted vectors

Requirements: 1.1, 1.2, 1.3
"""

from pathlib import Path

import numpy as np
import pytest

from return_prevention.core.model_registry import ModelRegistry
from return_prevention.core.scorer import score

# Path to the real pre-trained model
MODEL_PATH = str(
    Path(__file__).resolve().parent.parent / "ml" / "models" / "lgbm_return_risk.pkl"
)


@pytest.fixture(autouse=True)
def reset_and_load_model():
    """Reset the ModelRegistry singleton and load the real model before each test."""
    ModelRegistry._instance = None
    registry = ModelRegistry()
    registry.load(MODEL_PATH)
    yield
    ModelRegistry._instance = None


class TestHighRiskVector:
    """Smoke test: high return-risk inputs should produce probability > 0.5."""

    def test_high_risk_vector_above_half(self):
        """
        A feature vector with high return rates, size ambiguity, short dwell
        time, buy-now click, low rating, high seller rate, and active sale
        should yield probability > 0.5.
        """
        # FEATURE_COLS order:
        # category_return_rate, user_category_return_rate,
        # in_user_high_return_price_band, has_size_ambiguity,
        # page_dwell_seconds, is_buy_now, product_review_rating,
        # seller_return_rate, is_sale_active
        high_risk_vector = np.array([[
            0.45,   # category_return_rate (high)
            0.55,   # user_category_return_rate (high)
            1.0,    # in_user_high_return_price_band (True)
            1.0,    # has_size_ambiguity (True)
            3.0,    # page_dwell_seconds (very short — impulse buy)
            1.0,    # is_buy_now (True)
            2.1,    # product_review_rating (low)
            0.40,   # seller_return_rate (high)
            1.0,    # is_sale_active (True)
        ]])

        result = score(high_risk_vector)
        assert result > 0.5, f"Expected > 0.5 for high-risk vector, got {result}"


class TestLowRiskVector:
    """Smoke test: low return-risk inputs should produce probability < 0.5."""

    def test_low_risk_vector_below_half(self):
        """
        A feature vector with low return rates, no size ambiguity, long dwell
        time, add-to-cart, high rating, low seller rate, and no active sale
        should yield probability < 0.5.
        """
        low_risk_vector = np.array([[
            0.05,   # category_return_rate (low)
            0.03,   # user_category_return_rate (low)
            0.0,    # in_user_high_return_price_band (False)
            0.0,    # has_size_ambiguity (False)
            120.0,  # page_dwell_seconds (long — deliberate)
            0.0,    # is_buy_now (False — add to cart)
            4.8,    # product_review_rating (high)
            0.04,   # seller_return_rate (low)
            0.0,    # is_sale_active (False)
        ]])

        result = score(low_risk_vector)
        assert result < 0.5, f"Expected < 0.5 for low-risk vector, got {result}"


class TestOutputAlwaysInRange:
    """Output of score() must always be in [0.0, 1.0] for varied inputs."""

    @pytest.mark.parametrize("vector,description", [
        # 1. All zeros (minimum features)
        (np.array([[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]]),
         "all zeros"),
        # 2. All ones / maximums
        (np.array([[1.0, 1.0, 1.0, 1.0, 300.0, 1.0, 5.0, 1.0, 1.0]]),
         "all maximum values"),
        # 3. Mid-range balanced vector
        (np.array([[0.20, 0.20, 0.0, 0.0, 45.0, 0.0, 3.5, 0.15, 0.0]]),
         "mid-range balanced"),
        # 4. High dwell time, otherwise risky
        (np.array([[0.40, 0.50, 1.0, 1.0, 600.0, 1.0, 2.0, 0.35, 1.0]]),
         "high dwell time with risky features"),
        # 5. Zero dwell with safe profile
        (np.array([[0.08, 0.05, 0.0, 0.0, 0.0, 0.0, 4.5, 0.05, 0.0]]),
         "zero dwell with safe profile"),
        # 6. Mixed: high category rate but good user history
        (np.array([[0.50, 0.10, 0.0, 1.0, 30.0, 0.0, 3.0, 0.20, 0.0]]),
         "high category rate but good user history"),
        # 7. Mixed: low category rate but bad user history
        (np.array([[0.05, 0.60, 1.0, 0.0, 10.0, 1.0, 3.2, 0.10, 1.0]]),
         "low category rate but bad user history"),
        # 8. Extreme dwell time (very patient buyer)
        (np.array([[0.30, 0.25, 0.0, 1.0, 900.0, 0.0, 4.0, 0.18, 0.0]]),
         "extreme dwell time"),
        # 9. Perfect rating, all else risky
        (np.array([[0.45, 0.45, 1.0, 1.0, 5.0, 1.0, 5.0, 0.38, 1.0]]),
         "perfect rating with all else risky"),
        # 10. Very low rating, all else safe
        (np.array([[0.08, 0.06, 0.0, 0.0, 60.0, 0.0, 1.0, 0.06, 0.0]]),
         "very low rating with all else safe"),
    ])
    def test_score_in_valid_range(self, vector, description):
        """score() output must be in [0.0, 1.0] for: {description}."""
        result = score(vector)
        assert isinstance(result, float), f"Expected float, got {type(result)}"
        assert 0.0 <= result <= 1.0, (
            f"Score {result} out of range [0.0, 1.0] for vector: {description}"
        )
