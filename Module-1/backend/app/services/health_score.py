"""
Health Score Computer service.

Applies the weighted formula to compute the final health score,
breakdown, and condition label from component penalties.
Loads category-specific weights from SQLite category_weights table.
"""

import aiosqlite

from app.config.database import DATABASE_PATH
from app.models.results import HealthScoreResult, ScoreBreakdownResult

DEFAULT_WEIGHTS = (25.0, 25.0, 25.0, 25.0)


class HealthScoreComputer:
    """Computes the health score using category-specific weighted formula."""

    async def compute(
        self,
        anomaly_severity: float,
        defect_penalty: float,
        return_reason_penalty: float,
        wear_detection_penalty: float,
        category: str,
    ) -> HealthScoreResult:
        """
        Compute health score from component penalties and category weights.

        Formula: 100 - (w1*anomaly + w2*defect + w3*reason + w4*wear)
        Result is clamped to [0, 100] integer.

        Args:
            anomaly_severity: Anomaly severity score (0.0–1.0).
            defect_penalty: Defect penalty score (0.0–1.0).
            return_reason_penalty: Return reason penalty (0.0–1.0).
            wear_detection_penalty: Wear detection penalty (0.0–1.0).
            category: Product category for weight lookup.

        Returns:
            HealthScoreResult with score, breakdown, and condition label.
        """
        w1, w2, w3, w4 = await self._get_weights(category)

        # Compute weighted contributions
        w1_contribution = w1 * anomaly_severity
        w2_contribution = w2 * defect_penalty
        w3_contribution = w3 * return_reason_penalty
        w4_contribution = w4 * wear_detection_penalty

        # Apply formula and clamp to [0, 100]
        raw_score = 100 - (w1_contribution + w2_contribution + w3_contribution + w4_contribution)
        health_score = int(max(0, min(100, raw_score)))

        breakdown = ScoreBreakdownResult(
            w1_anomaly_contribution=w1_contribution,
            w2_defect_contribution=w2_contribution,
            w3_reason_contribution=w3_contribution,
            w4_wear_contribution=w4_contribution,
        )

        condition = self._map_condition(health_score)

        return HealthScoreResult(
            health_score=health_score,
            breakdown=breakdown,
            condition=condition,
        )

    async def _get_weights(self, category: str) -> tuple[float, float, float, float]:
        """Load category weights from SQLite.

        Falls back to DEFAULT_WEIGHTS (25, 25, 25, 25) if category not found.
        """
        try:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                cursor = await db.execute(
                    "SELECT w1_anomaly, w2_defect, w3_reason, w4_wear "
                    "FROM category_weights WHERE category = ?",
                    (category,),
                )
                row = await cursor.fetchone()
                if row is not None:
                    return (row[0], row[1], row[2], row[3])
                return DEFAULT_WEIGHTS
        except Exception:
            # On DB failure, use default weights to allow computation to proceed
            return DEFAULT_WEIGHTS

    @staticmethod
    def _map_condition(health_score: int) -> str:
        """Map health score to condition label.

        >90 → Excellent, >70 → Good, >50 → Fair, <=50 → Poor
        """
        if health_score > 90:
            return "Excellent"
        elif health_score > 70:
            return "Good"
        elif health_score > 50:
            return "Fair"
        else:
            return "Poor"
