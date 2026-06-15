"""
return_prevention/config.py

Application settings loaded via pydantic-settings BaseSettings.

RISK_THRESHOLD validation:
  - Must be a float in [0.0, 1.0].
  - If an invalid value is supplied at load time the module catches the
    error, retains the last valid value (default 0.6), and logs a
    structured error via the stdlib `logging` module — it does NOT raise.
"""

from __future__ import annotations

import logging
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default value kept here so the validator can fall back to it explicitly.
# ---------------------------------------------------------------------------
_DEFAULT_RISK_THRESHOLD: float = 0.6


class Settings(BaseSettings):
    """Centralised application configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # Extra env vars are silently ignored so the service doesn't crash
        # when the host environment has unrelated variables set.
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Fields
    # ------------------------------------------------------------------
    MODEL_PATH: str = "ml/models/lgbm_return_risk.pkl"
    RISK_THRESHOLD: float = _DEFAULT_RISK_THRESHOLD
    DB_URL: str = "sqlite:///./return_prevention.db"
    TAXONOMY_PATH: str = "data/taxonomy.json"
    CUSTOMER_PROFILE_BASE_URL: str = "http://localhost:8001"
    GREEN_COIN_BASE_URL: str = "http://localhost:8002"
    LOCAL_LLM_URL: Optional[str] = None
    INTERNAL_HOSTS: list[str] = ["127.0.0.1", "localhost"]

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------
    @field_validator("RISK_THRESHOLD", mode="before")
    @classmethod
    def validate_risk_threshold(cls, v: object) -> float:
        """
        Validate that RISK_THRESHOLD is a float in [0.0, 1.0].

        On any validation failure:
          - Log a structured ERROR (does NOT raise).
          - Return the default value so the service continues.
        """
        try:
            value = float(v)
        except (TypeError, ValueError):
            logger.error(
                "config_error field=RISK_THRESHOLD invalid_value=%r "
                "reason='not a valid float' fallback=%s",
                v,
                _DEFAULT_RISK_THRESHOLD,
            )
            return _DEFAULT_RISK_THRESHOLD

        if not (0.0 <= value <= 1.0):
            logger.error(
                "config_error field=RISK_THRESHOLD invalid_value=%s "
                "reason='value outside [0.0, 1.0]' fallback=%s",
                value,
                _DEFAULT_RISK_THRESHOLD,
            )
            return _DEFAULT_RISK_THRESHOLD

        return value


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

def _build_settings() -> Settings:
    """
    Construct the Settings singleton, gracefully handling any unexpected
    validation errors during model construction.
    """
    try:
        return Settings()
    except Exception as exc:
        logger.error(
            "config_error reason='unexpected error loading settings' detail=%s",
            exc,
        )
        # Return a fully-default Settings object, bypassing env vars.
        return Settings.model_construct(
            MODEL_PATH="ml/models/lgbm_return_risk.pkl",
            RISK_THRESHOLD=_DEFAULT_RISK_THRESHOLD,
            DB_URL="sqlite:///./return_prevention.db",
            TAXONOMY_PATH="data/taxonomy.json",
            CUSTOMER_PROFILE_BASE_URL="http://localhost:8001",
            GREEN_COIN_BASE_URL="http://localhost:8002",
            LOCAL_LLM_URL=None,
            INTERNAL_HOSTS=["127.0.0.1", "localhost"],
        )


settings: Settings = _build_settings()
