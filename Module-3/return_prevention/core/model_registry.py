"""
return_prevention/core/model_registry.py

Singleton model registry for the LightGBM return-risk classifier.

Provides thread-safe load, reload, predict_proba, and feature_importances
access to the serialized LightGBM model.

Requirements: 4.1, 4.5, 4.6
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np

logger = logging.getLogger(__name__)

# ── Feature column order — must match ml/train.py exactly ─────────────────────
FEATURE_COLS: list[str] = [
    "category_return_rate",
    "user_category_return_rate",
    "in_user_high_return_price_band",
    "has_size_ambiguity",
    "page_dwell_seconds",
    "is_buy_now",
    "product_review_rating",
    "seller_return_rate",
    "is_sale_active",
]


class ModelRegistry:
    """
    Singleton holder for the LightGBM model.

    All public methods are protected by a threading.RLock to allow
    safe concurrent access and hot-reload without service restart.
    """

    _instance: ModelRegistry | None = None
    _init_lock: threading.Lock = threading.Lock()

    def __new__(cls) -> ModelRegistry:
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._lock = threading.RLock()
                    instance._model = None
                    cls._instance = instance
        return cls._instance

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, path: str) -> None:
        """
        Load a serialized model from disk into memory.

        Called at service startup. Raises RuntimeError if the file is
        missing or cannot be deserialized.
        """
        model_path = Path(path)

        if not model_path.exists():
            raise RuntimeError(
                f"Model file not found: {model_path.resolve()}"
            )

        try:
            model = joblib.load(model_path)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to load model from {model_path.resolve()}: {exc}"
            ) from exc

        with self._lock:
            self._model = model

        logger.info("model_loaded path=%s", path)

    def reload(self, path: str) -> datetime:
        """
        Atomically swap the in-memory model with a freshly loaded one.

        Returns the file's modification time as a UTC datetime.
        Raises RuntimeError if the file is missing or corrupt, but
        retains the previous model in that case.
        """
        model_path = Path(path)

        if not model_path.exists():
            raise RuntimeError(
                f"Model file not found for reload: {model_path.resolve()}"
            )

        try:
            new_model = joblib.load(model_path)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to reload model from {model_path.resolve()}: {exc}"
            ) from exc

        # Get file mtime as UTC datetime
        file_mtime = datetime.fromtimestamp(
            model_path.stat().st_mtime, tz=timezone.utc
        )

        # Atomic swap under lock
        with self._lock:
            self._model = new_model

        logger.info("model_reloaded path=%s mtime=%s", path, file_mtime.isoformat())
        return file_mtime

    def predict_proba(self, X: np.ndarray) -> float:
        """
        Return the predicted probability for the positive (return) class.

        Calls _model.predict_proba(X)[:, 1][0] under a read-lock.
        Raises RuntimeError if no model is currently loaded.
        """
        with self._lock:
            if self._model is None:
                raise RuntimeError(
                    "Model not loaded. Call load() or reload() first."
                )
            probabilities = self._model.predict_proba(X)

        return float(probabilities[:, 1][0])

    @property
    def feature_importances(self) -> dict[str, float]:
        """
        Return a mapping of feature name → importance score from the
        loaded LightGBM model's gain-based feature importances.
        """
        with self._lock:
            if self._model is None:
                raise RuntimeError(
                    "Model not loaded. Call load() or reload() first."
                )
            importances = self._model.feature_importances_

        return dict(zip(FEATURE_COLS, (float(v) for v in importances)))
