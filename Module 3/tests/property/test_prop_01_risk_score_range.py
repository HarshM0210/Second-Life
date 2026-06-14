"""
Property-based test for Property 1 — Risk Score is Always a Valid Probability.

For any valid combination of the 9 input features (each within their documented
ranges), the RiskScorer SHALL return a float value in the closed interval [0.0, 1.0].

**Validates: Requirements 1.1, 1.3**
"""

from pathlib import Path

import numpy as np
import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from return_prevention.core.model_registry import ModelRegistry
from return_prevention.core.scorer import score

# Path to the real pre-trained model
MODEL_PATH = str(
    Path(__file__).resolve().parent.parent.parent / "ml" / "models" / "lgbm_return_risk.pkl"
)


def feature_vector_strategy():
    """
    Generate 9-dimensional feature vectors within documented ranges.

    Feature ranges:
      - category_return_rate: [0.0, 1.0]
      - user_category_return_rate: [0.0, 1.0]
      - in_user_high_return_price_band: [0.0, 1.0] (boolean as float)
      - has_size_ambiguity: [0.0, 1.0] (boolean as float)
      - page_dwell_seconds: [0.0, 600.0]
      - is_buy_now: [0.0, 1.0] (boolean as float)
      - product_review_rating: [0.0, 5.0]
      - seller_return_rate: [0.0, 1.0]
      - is_sale_active: [0.0, 1.0] (boolean as float)
    """
    return st.tuples(
        st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),      # category_return_rate
        st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),      # user_category_return_rate
        st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),      # in_user_high_return_price_band
        st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),      # has_size_ambiguity
        st.floats(min_value=0.0, max_value=600.0, allow_nan=False, allow_infinity=False),    # page_dwell_seconds
        st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),      # is_buy_now
        st.floats(min_value=0.0, max_value=5.0, allow_nan=False, allow_infinity=False),      # product_review_rating
        st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),      # seller_return_rate
        st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),      # is_sale_active
    )


@pytest.fixture(autouse=True)
def reset_and_load_model():
    """Reset the ModelRegistry singleton and load the real model before each test."""
    ModelRegistry._instance = None
    registry = ModelRegistry()
    registry.load(MODEL_PATH)
    yield
    ModelRegistry._instance = None


@given(features=feature_vector_strategy())
@settings(
    max_examples=200,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_risk_score_always_valid_probability(features, reset_and_load_model):
    """
    Property 1: Score is Always a Valid Probability.

    For any valid 9-feature vector within documented ranges, score() must
    return a float in [0.0, 1.0].

    **Validates: Requirements 1.1, 1.3**
    """
    vector = np.array([list(features)])

    result = score(vector)

    assert isinstance(result, float), f"Expected float, got {type(result)}"
    assert 0.0 <= result <= 1.0, (
        f"Risk score {result} is outside valid probability range [0.0, 1.0] "
        f"for feature vector: {features}"
    )
