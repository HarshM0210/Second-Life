"""
Fraud Confidence Aggregator service.

Merges the social signal, wear detection penalty, and behavioural score
into a single fraud_confidence value using a weighted sum with proportional
redistribution when signals are missing.

Requirements: 11.1, 11.2, 11.3, 11.4, 11.5
"""

import logging
import time
from typing import Final

logger = logging.getLogger(__name__)

# Default weights (must sum to 1.0) — Requirement 11.1
_DEFAULT_SOCIAL_WEIGHT: Final[float] = 0.40
_DEFAULT_WEAR_WEIGHT: Final[float] = 0.35
_DEFAULT_BEHAVIOURAL_WEIGHT: Final[float] = 0.25

# Timeout budget in seconds (Requirement 11.5: 50ms)
_TIMEOUT_MS: Final[float] = 50.0


class FraudAggregator:
    """Aggregates fraud signals into a single fraud_confidence score.

    Uses a configurable weighted sum with proportional weight redistribution
    when one or more signals are missing (None or social scan not performed).
    """

    def __init__(
        self,
        social_weight: float = _DEFAULT_SOCIAL_WEIGHT,
        wear_weight: float = _DEFAULT_WEAR_WEIGHT,
        behavioural_weight: float = _DEFAULT_BEHAVIOURAL_WEIGHT,
    ) -> None:
        """Initialize with configurable weights.

        Args:
            social_weight: Weight for social signal (default 0.40).
            wear_weight: Weight for wear detection penalty (default 0.35).
            behavioural_weight: Weight for behavioural score (default 0.25).

        Raises:
            ValueError: If weights do not sum to 1.0 (within tolerance).
        """
        total = social_weight + wear_weight + behavioural_weight
        if abs(total - 1.0) > 1e-9:
            raise ValueError(
                f"Weights must sum to 1.0, got {total:.6f} "
                f"(social={social_weight}, wear={wear_weight}, "
                f"behavioural={behavioural_weight})"
            )

        self._social_weight = social_weight
        self._wear_weight = wear_weight
        self._behavioural_weight = behavioural_weight

    def aggregate(
        self,
        social_signal: float | None,
        wear_penalty: float,
        behavioural_score: float,
        social_scan_performed: bool,
    ) -> float:
        """Compute aggregated fraud_confidence from available signals.

        When social_scan_performed is False or social_signal is None, the
        social weight is proportionally redistributed to wear and behavioural
        weights so that the absence of social data neither inflates nor
        deflates the score (Requirement 11.3).

        When any signal is missing (None), treat it as 0.0 and redistribute
        its weight proportionally to the remaining signals (Requirement 11.4).

        Args:
            social_signal: Social fraud signal score (0.0-1.0), or None if
                not available.
            wear_penalty: Wear detection penalty (0.0-1.0).
            behavioural_score: Behavioural fraud score (0.0-1.0).
            social_scan_performed: Whether the social scan was executed.

        Returns:
            fraud_confidence clamped to [0.0, 1.0].
        """
        start_time = time.perf_counter()

        # Determine which signals are available
        # Social signal is unavailable if scan not performed or value is None
        social_available = social_scan_performed and social_signal is not None
        wear_available = wear_penalty is not None
        behavioural_available = behavioural_score is not None

        # Build list of (weight, value) for available signals
        # and accumulate weight to redistribute from missing signals
        weight_to_redistribute = 0.0
        available_signals: list[tuple[float, float]] = []

        if social_available:
            available_signals.append((self._social_weight, social_signal))
        else:
            weight_to_redistribute += self._social_weight
            if not social_scan_performed:
                logger.debug("Social scan not performed, redistributing social weight")
            elif social_signal is None:
                logger.debug("Social signal is None, redistributing social weight")

        if wear_available:
            available_signals.append((self._wear_weight, wear_penalty))
        else:
            weight_to_redistribute += self._wear_weight
            logger.debug("Wear penalty is None, redistributing wear weight")

        if behavioural_available:
            available_signals.append((self._behavioural_weight, behavioural_score))
        else:
            weight_to_redistribute += self._behavioural_weight
            logger.debug("Behavioural score is None, redistributing behavioural weight")

        # If no signals are available, fraud confidence is 0.0
        if not available_signals:
            logger.warning("No fraud signals available, returning 0.0")
            return 0.0

        # Proportionally redistribute missing weights across available signals
        total_available_weight = sum(w for w, _ in available_signals)

        # Compute weighted sum with redistributed weights
        fraud_confidence = 0.0
        for base_weight, value in available_signals:
            # New weight = base_weight + proportional share of redistributed weight
            redistributed_share = (base_weight / total_available_weight) * weight_to_redistribute
            effective_weight = base_weight + redistributed_share
            fraud_confidence += effective_weight * value

        # Clamp to [0.0, 1.0]
        fraud_confidence = max(0.0, min(1.0, fraud_confidence))

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        if elapsed_ms > _TIMEOUT_MS:
            logger.warning(
                "Fraud aggregation took %.1fms, exceeding 50ms budget", elapsed_ms
            )

        return fraud_confidence
