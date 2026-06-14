"""
Intent Classifier service.

Maps structured Q&A answers to return_reason_penalty scores using keyword mapping.
Detects Q&A-to-CV inconsistencies for fraud signal escalation.

Requirements: 8.1, 8.2, 8.3, 8.4, 8.5
"""

import time
from dataclasses import dataclass, field

from app.models.results import IntentResult


# ---------------------------------------------------------------------------
# Keyword mapping tables
# ---------------------------------------------------------------------------

# HIGH penalty answers — indicate serious functional issues
# 0.35 for non-functional / completely broken
HIGH_PENALTY_035: list[str] = [
    "not functional — does not power on / completely broken",
    "not functional",
    "does not power on",
    "completely broken",
    "significant damage (broken screen, crushed, burnt)",
    "severe damage",
    "broken screen",
    "crushed",
    "burnt",
    "significant damage (torn, broken fastening)",
    "leaking or crushed",
]

# 0.25 for partially functional claims
HIGH_PENALTY_025: list[str] = [
    "partially functional — some features not working",
    "partially functional",
    "some features not working",
    "item is defective / not working",
    "item defective or not working",
    "moderate damage (cracked casing, significant scratches)",
    "significant damage — contents may be compromised",
]

# MEDIUM penalty answers — "not as described" claims (0.15)
MEDIUM_PENALTY: list[str] = [
    "item not as described in listing",
    "item not as described",
    "not as described",
    "style / colour not as shown in images",
    "quality not as expected (fabric, stitching)",
    "quality not as expected",
    "received wrong item",
    "wrong item delivered",
    "wrong item received",
    "item damaged on arrival",
    "physical damage on arrival",
    "compatibility issue (wrong model/version)",
    "compatibility issue",
]

# LOW penalty answers — preference or cosmetic/fit reasons
# 0.05 for preference (changed mind)
LOW_PENALTY_005: list[str] = [
    "changed my mind / no longer needed",
    "changed my mind",
    "no longer needed",
]

# 0.10 for cosmetic/fit reasons (wrong size)
LOW_PENALTY_010: list[str] = [
    "wrong size — too small",
    "wrong size — too large",
    "wrong size",
    "too small",
    "too large",
    "minor cosmetic damage (light scratches, small dents)",
    "minor cosmetic damage",
    "missing parts or accessories",
]

# Answers that indicate "never used" — used for inconsistency detection
NEVER_USED_INDICATORS: list[str] = [
    "never used — still in original packaging",
    "never worn — tags still attached",
    "never used — completely unused",
    "never used",
    "never worn",
]


class IntentClassifier:
    """Classifies return intent from structured Q&A answers using keyword mapping.

    Maps the 'return_reason' and related Q&A answers to a penalty category
    and numeric penalty score. Also detects Q&A-to-CV inconsistencies.
    """

    def classify(self, qa_answers: dict[str, str], category: str) -> IntentResult:
        """Classify return intent from Q&A answers.

        Completes within 200ms. Uses keyword mapping (no model training).

        Args:
            qa_answers: Key-value pairs of Q&A responses.
            category: Product category (e.g., "Electronics", "Clothing & Footwear").

        Returns:
            IntentResult with penalty score, category, flags, and unclassified status.
        """
        start_time = time.perf_counter()

        # Primary signal: return_reason answer
        return_reason = qa_answers.get("return_reason", "").strip().lower()

        # Secondary signals from other answers that may indicate severity
        functional_status = qa_answers.get("functional_status", "").strip().lower()
        physical_condition = qa_answers.get("physical_condition", "").strip().lower()

        # Attempt classification from most specific to least specific
        penalty, penalty_category, unclassified = self._map_to_penalty(
            return_reason, functional_status, physical_condition, category
        )

        # Ensure we stay within 200ms budget
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        assert elapsed_ms < 200, f"Intent classification exceeded 200ms: {elapsed_ms:.1f}ms"

        return IntentResult(
            return_reason_penalty=penalty,
            penalty_category=penalty_category,
            inconsistency_flags=[],
            unclassified=unclassified,
        )

    def check_inconsistencies(
        self, qa_answers: dict[str, str], wear_detection_penalty: float
    ) -> list[str]:
        """Check for Q&A-to-CV inconsistencies.

        Detects cases where Q&A indicates "never used" but wear detection
        found evidence of use (wear_detection_penalty > 0).

        Args:
            qa_answers: Key-value pairs of Q&A responses.
            wear_detection_penalty: The penalty from the Wear Detector (0.0-1.0).

        Returns:
            List of inconsistency flag strings for the Fraud Aggregator.
        """
        flags: list[str] = []

        if wear_detection_penalty > 0:
            # Check multiple Q&A fields that could indicate "never used"
            fields_to_check = [
                qa_answers.get("ownership_duration", ""),
                qa_answers.get("wear_history", ""),
                qa_answers.get("usage_extent", ""),
            ]

            for field_value in fields_to_check:
                normalized = field_value.strip().lower()
                if any(indicator in normalized for indicator in NEVER_USED_INDICATORS):
                    flags.append("never_used_but_wear_detected")
                    break

        return flags

    def _map_to_penalty(
        self,
        return_reason: str,
        functional_status: str,
        physical_condition: str,
        category: str,
    ) -> tuple[float, str, bool]:
        """Map answer text to penalty value using keyword matching.

        Uses a "most severe wins" approach: checks all signals and returns
        the highest penalty found across return_reason, functional_status,
        and physical_condition.

        Returns:
            Tuple of (penalty_value, penalty_category, unclassified).
        """
        # Collect all signals to find the most severe match
        all_fields = [return_reason, functional_status, physical_condition]

        # Check HIGH penalty (0.35) — non-functional / completely broken
        for field_val in all_fields:
            if self._matches_any(field_val, HIGH_PENALTY_035):
                return 0.35, "high", False

        # Check HIGH penalty (0.25) — partially functional
        for field_val in all_fields:
            if self._matches_any(field_val, HIGH_PENALTY_025):
                return 0.25, "high", False

        # Check LOW penalty (0.05) — preference / changed mind
        if self._matches_any(return_reason, LOW_PENALTY_005):
            return 0.05, "low", False

        # Check LOW penalty (0.10) — cosmetic / fit / wrong size
        if self._matches_any(return_reason, LOW_PENALTY_010):
            return 0.10, "low", False

        # Check MEDIUM penalty (0.15) — not as described
        if self._matches_any(return_reason, MEDIUM_PENALTY):
            return 0.15, "medium", False

        # Check physical condition for low severity
        if self._matches_any(physical_condition, LOW_PENALTY_010):
            return 0.10, "low", False

        # Fallback: unclassifiable → assign medium (0.15) with unclassified flag
        return 0.15, "medium", True

    @staticmethod
    def _matches_any(text: str, keywords: list[str]) -> bool:
        """Check if text matches any of the keyword phrases.

        Uses substring matching (case-insensitive) for flexibility.
        """
        if not text:
            return False
        for keyword in keywords:
            if keyword in text or text in keyword:
                return True
        return False
