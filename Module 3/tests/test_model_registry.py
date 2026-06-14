"""
Unit tests for return_prevention/core/model_registry.py

Tests cover:
- Loading the existing ml/models/lgbm_return_risk.pkl without exception
- predict_proba returns a float in [0.0, 1.0] for a known feature vector
- reload with a freshly trained temp model updates feature_importances
- reload with a corrupt file retains the previous model and raises RuntimeError

Requirements: 4.1, 4.5
"""

import os
from pathlib import Path

import joblib
import lightgbm as lgb
import numpy as np
import pytest

from return_prevention.core.model_registry import FEATURE_COLS, ModelRegistry

# Path to the real pre-trained model
MODEL_PATH = str(
    Path(__file__).resolve().parent.parent / "ml" / "models" / "lgbm_return_risk.pkl"
)


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the ModelRegistry singleton before each test for isolation."""
    ModelRegistry._instance = None
    yield
    ModelRegistry._instance = None


@pytest.fixture
def registry():
    """Return a fresh ModelRegistry instance."""
    return ModelRegistry()


class TestLoadExistingModel:
    """Test that the existing lgbm_return_risk.pkl loads without exception."""

    def test_load_no_exception(self, registry):
        """Loading the real model file should not raise any exception."""
        registry.load(MODEL_PATH)

    def test_load_sets_model(self, registry):
        """After load, the model should be available for prediction."""
        registry.load(MODEL_PATH)
        # feature_importances should be accessible after load
        importances = registry.feature_importances
        assert isinstance(importances, dict)
        assert len(importances) == 9


class TestPredictProba:
    """Test that predict_proba returns a float in [0.0, 1.0]."""

    def test_predict_proba_returns_valid_probability(self, registry):
        """predict_proba on a known feature vector returns float in [0.0, 1.0]."""
        registry.load(MODEL_PATH)

        # Construct a realistic feature vector (shape 1x9)
        # Features: category_return_rate, user_category_return_rate,
        #           in_user_high_return_price_band, has_size_ambiguity,
        #           page_dwell_seconds, is_buy_now, product_review_rating,
        #           seller_return_rate, is_sale_active
        feature_vector = np.array([[
            0.25,   # category_return_rate
            0.30,   # user_category_return_rate
            1.0,    # in_user_high_return_price_band (True)
            1.0,    # has_size_ambiguity (True)
            15.0,   # page_dwell_seconds
            0.0,    # is_buy_now (False)
            3.8,    # product_review_rating
            0.18,   # seller_return_rate
            0.0,    # is_sale_active (False)
        ]])

        result = registry.predict_proba(feature_vector)

        assert isinstance(result, float)
        assert 0.0 <= result <= 1.0

    def test_predict_proba_low_risk_vector(self, registry):
        """A low-risk feature vector should still produce a valid probability."""
        registry.load(MODEL_PATH)

        # Low risk: low return rates, long dwell time, high rating
        feature_vector = np.array([[
            0.05,   # category_return_rate (low)
            0.02,   # user_category_return_rate (low)
            0.0,    # in_user_high_return_price_band (False)
            0.0,    # has_size_ambiguity (False)
            120.0,  # page_dwell_seconds (long dwell)
            0.0,    # is_buy_now (False - deliberate)
            4.8,    # product_review_rating (high)
            0.03,   # seller_return_rate (low)
            0.0,    # is_sale_active (False)
        ]])

        result = registry.predict_proba(feature_vector)

        assert isinstance(result, float)
        assert 0.0 <= result <= 1.0

    def test_predict_proba_raises_when_model_not_loaded(self, registry):
        """predict_proba should raise RuntimeError if no model is loaded."""
        with pytest.raises(RuntimeError, match="Model not loaded"):
            registry.predict_proba(np.zeros((1, 9)))


class TestReloadWithFreshModel:
    """Test that reload with a freshly trained temp model updates feature_importances."""

    def test_reload_updates_feature_importances(self, registry, tmp_path):
        """Reloading with a new model should update the feature importances."""
        # Load the original model first
        registry.load(MODEL_PATH)
        original_importances = registry.feature_importances

        # Train a tiny LGBMClassifier (sklearn API) with different data
        rng = np.random.default_rng(42)
        n_samples = 200
        X_train = rng.random((n_samples, 9))
        # Create a simple binary target correlated with the first feature
        y_train = (X_train[:, 0] > 0.5).astype(int)

        new_model = lgb.LGBMClassifier(
            n_estimators=10,
            num_leaves=4,
            learning_rate=0.1,
            verbose=-1,
        )
        new_model.fit(X_train, y_train)

        # Save the new model to a temp file
        temp_model_path = tmp_path / "new_model.pkl"
        joblib.dump(new_model, temp_model_path)

        # Reload with the new model
        result_mtime = registry.reload(str(temp_model_path))

        # Verify reload returns a datetime
        from datetime import datetime
        assert isinstance(result_mtime, datetime)

        # feature_importances should now be different from the original
        new_importances = registry.feature_importances
        assert isinstance(new_importances, dict)
        assert len(new_importances) == 9
        assert set(new_importances.keys()) == set(FEATURE_COLS)

        # The importances should have changed (different training data)
        assert new_importances != original_importances


class TestReloadWithCorruptFile:
    """Test that reload with a corrupt file retains the previous model and raises error."""

    def test_reload_corrupt_file_raises_and_retains_model(self, registry, tmp_path):
        """Reload with a corrupt file should raise RuntimeError but keep old model."""
        # Load the real model first
        registry.load(MODEL_PATH)

        # Record the original feature importances
        original_importances = registry.feature_importances

        # Create a corrupt file with random bytes
        corrupt_path = tmp_path / "corrupt_model.pkl"
        corrupt_path.write_bytes(os.urandom(256))

        # Reload should raise RuntimeError
        with pytest.raises(RuntimeError, match="Failed to reload model"):
            registry.reload(str(corrupt_path))

        # The previous model should still be retained
        retained_importances = registry.feature_importances
        assert retained_importances == original_importances

        # predict_proba should still work with the retained model
        feature_vector = np.array([[0.2, 0.3, 1.0, 0.0, 10.0, 1.0, 4.0, 0.15, 0.0]])
        result = registry.predict_proba(feature_vector)
        assert 0.0 <= result <= 1.0

    def test_reload_missing_file_raises_and_retains_model(self, registry, tmp_path):
        """Reload with a non-existent file should raise RuntimeError but keep old model."""
        # Load the real model first
        registry.load(MODEL_PATH)
        original_importances = registry.feature_importances

        # Attempt to reload from a non-existent path
        missing_path = str(tmp_path / "does_not_exist.pkl")

        with pytest.raises(RuntimeError, match="Model file not found"):
            registry.reload(missing_path)

        # Previous model should be retained
        assert registry.feature_importances == original_importances
