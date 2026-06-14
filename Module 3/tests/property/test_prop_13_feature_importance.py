"""
Property Test 13 — Feature Importance Response Contains All 9 Features

Loading the model via ModelRegistry and accessing feature_importances SHALL
return exactly 9 keys matching FEATURE_COLS with all non-negative float values.

**Validates: Requirements 4.7**
"""

from __future__ import annotations

from pathlib import Path

from hypothesis import given, settings as h_settings
from hypothesis import strategies as st

from return_prevention.core.model_registry import FEATURE_COLS, ModelRegistry

# Path to the real pre-trained model
MODEL_PATH = str(
    Path(__file__).resolve().parent.parent.parent / "ml" / "models" / "lgbm_return_risk.pkl"
)


@given(trigger=st.just(True))
@h_settings(max_examples=1, deadline=10000)
def test_feature_importances_contains_all_9_features(trigger):
    """
    Property 13: Feature Importance Response Contains All 9 Features.

    Load the real LightGBM model via ModelRegistry and verify that
    feature_importances returns exactly 9 keys matching FEATURE_COLS
    with all non-negative float values.

    **Validates: Requirements 4.7**
    """
    # Reset and load model
    ModelRegistry._instance = None
    registry = ModelRegistry()
    registry.load(MODEL_PATH)

    try:
        importances = registry.feature_importances

        # Assert exactly 9 keys
        assert len(importances) == 9, (
            f"Expected exactly 9 feature importance keys, got {len(importances)}: "
            f"{list(importances.keys())}"
        )

        # Assert all keys match FEATURE_COLS
        assert set(importances.keys()) == set(FEATURE_COLS), (
            f"Feature importance keys do not match FEATURE_COLS.\n"
            f"Expected: {sorted(FEATURE_COLS)}\n"
            f"Got: {sorted(importances.keys())}"
        )

        # Assert all values are non-negative floats
        for key, value in importances.items():
            assert isinstance(value, float), (
                f"Feature importance for '{key}' is not a float: {type(value)}"
            )
            assert value >= 0.0, (
                f"Feature importance for '{key}' is negative: {value}"
            )
    finally:
        ModelRegistry._instance = None
