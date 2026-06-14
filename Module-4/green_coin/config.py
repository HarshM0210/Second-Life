"""
green_coin/config.py

Application settings loaded via pydantic-settings BaseSettings.

Mirrors the configuration style used by Module 3 (return_prevention) so the
two services share conventions. The Green Coin service is expected to run on
port 8002 — Module 3's ``GREEN_COIN_BASE_URL`` defaults to
``http://localhost:8002`` and posts purchase-avoidance events to
``/api/v4/purchase-avoidance``.

COIN_MULTIPLIER and EARN_CAP_PER_EVENT are validated defensively: an invalid
value is logged and replaced with a safe default rather than crashing the
service at startup.
"""

from __future__ import annotations

import logging

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Defaults kept module-level so validators can fall back to them explicitly.
_DEFAULT_COIN_MULTIPLIER: int = 10
_DEFAULT_EARN_CAP: int = 500
_DEFAULT_FRAUD_DAILY_THRESHOLD: int = 2000


class Settings(BaseSettings):
    """Centralised application configuration for the Green Coin service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Fields
    # ------------------------------------------------------------------
    DB_URL: str = "sqlite:///./green_coin.db"
    REWARDS_PATH: str = "data/rewards.json"

    # 1 kg CO2e avoided == COIN_MULTIPLIER Green Coins.
    COIN_MULTIPLIER: int = _DEFAULT_COIN_MULTIPLIER

    # Anti-abuse: maximum coins issued for a single disposition earn event.
    EARN_CAP_PER_EVENT: int = _DEFAULT_EARN_CAP

    # Anti-abuse: flag a user who earns more than this many coins in 24h.
    FRAUD_DAILY_THRESHOLD: int = _DEFAULT_FRAUD_DAILY_THRESHOLD

    # Coins granted when a customer keeps an item after a Module 3 nudge.
    KEPT_AFTER_NUDGE_COINS: int = 40

    # Streak reset window — a gap larger than this (hours) resets the streak.
    STREAK_RESET_HOURS: int = 48

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------
    @field_validator("COIN_MULTIPLIER", mode="before")
    @classmethod
    def _validate_multiplier(cls, v: object) -> int:
        return cls._positive_int(v, _DEFAULT_COIN_MULTIPLIER, "COIN_MULTIPLIER")

    @field_validator("EARN_CAP_PER_EVENT", mode="before")
    @classmethod
    def _validate_cap(cls, v: object) -> int:
        return cls._positive_int(v, _DEFAULT_EARN_CAP, "EARN_CAP_PER_EVENT")

    @field_validator("FRAUD_DAILY_THRESHOLD", mode="before")
    @classmethod
    def _validate_fraud_threshold(cls, v: object) -> int:
        return cls._positive_int(v, _DEFAULT_FRAUD_DAILY_THRESHOLD, "FRAUD_DAILY_THRESHOLD")

    @staticmethod
    def _positive_int(v: object, fallback: int, field: str) -> int:
        """Coerce ``v`` to a positive int, falling back (and logging) on failure."""
        try:
            value = int(v)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            logger.error(
                "config_error field=%s invalid_value=%r reason='not an int' fallback=%s",
                field, v, fallback,
            )
            return fallback
        if value <= 0:
            logger.error(
                "config_error field=%s invalid_value=%s reason='must be > 0' fallback=%s",
                field, value, fallback,
            )
            return fallback
        return value


def _build_settings() -> Settings:
    """Construct the Settings singleton, degrading gracefully on failure."""
    try:
        return Settings()
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("config_error reason='unexpected error loading settings' detail=%s", exc)
        return Settings.model_construct(
            DB_URL="sqlite:///./green_coin.db",
            REWARDS_PATH="data/rewards.json",
            COIN_MULTIPLIER=_DEFAULT_COIN_MULTIPLIER,
            EARN_CAP_PER_EVENT=_DEFAULT_EARN_CAP,
            FRAUD_DAILY_THRESHOLD=_DEFAULT_FRAUD_DAILY_THRESHOLD,
            KEPT_AFTER_NUDGE_COINS=40,
            STREAK_RESET_HOURS=48,
        )


settings: Settings = _build_settings()
