"""
return_prevention/core/scorer.py

Thin wrapper around ModelRegistry.predict_proba that validates and clamps
the returned probability to [0.0, 1.0].

Requirements: 1.1, 1.2
"""

from __future__ import annotations

import logging

import numpy as np

from return_prevention.core.model_registry import ModelRegistry

logger = logging.getLogger(__name__)


def score(feature_vector: np.ndarray) -> float:
    """
    Score a feature vector using the loaded LightGBM model.

    Calls ModelRegistry().predict_proba(feature_vector), validates the
    return value is in [0.0, 1.0], clamps if outside (logging an error),
    and returns the float probability.

    Parameters
    ----------
    feature_vector : np.ndarray
        A numpy array of shape (1, 9) in the exact FEATURE_COLS column order.

    Returns
    -------
    float
        The predicted return probability, guaranteed in [0.0, 1.0].
    """
    registry = ModelRegistry()
    raw_score = registry.predict_proba(feature_vector)

    if raw_score < 0.0:
        logger.error(
            "predict_proba returned value below 0.0: %f — clamping to 0.0",
            raw_score,
        )
        return 0.0

    if raw_score > 1.0:
        logger.error(
            "predict_proba returned value above 1.0: %f — clamping to 1.0",
            raw_score,
        )
        return 1.0

    return float(raw_score)
