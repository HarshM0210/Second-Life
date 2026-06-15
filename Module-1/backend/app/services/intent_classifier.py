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
    # Clothing & Footwear heavy-use / condition signals (Fix 1: previously ignored)
    "worn multiple times",
    "yes — washed multiple times",
    "yes — visible stain or noticeable odour",
    "all tags removed",
    "significant wear — clearly used outdoors",
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
    # Clothing & Footwear moderate condition signals (Fix 1: previously ignored)
    "some tags removed",
    "minor — very faint mark or slight odour",
    "visible sole wear or scuffing",
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

        # Map the full set of condition-bearing Q&A answers to a penalty.
        # (Fix 1: previously only return_reason/functional_status/physical_condition
        # were inspected, so clothing damage fields were silently ignored.)
        penalty, penalty_category, unclassified = self._map_to_penalty(
            qa_answers, category
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
        qa_answers: dict[str, str],
        category: str,
    ) -> tuple[float, str, bool]:
        """Map Q&A answers to a penalty value using keyword matching.

        Uses a "most severe wins" approach across **every** condition-bearing
        field, not just the return reason. The severity cascade is:

            HIGH 0.35  ->  HIGH 0.25  ->  MEDIUM 0.15  ->  LOW 0.10  ->  LOW 0.05

        Reason-type semantics (changed-mind / wrong-size) remain keyed off the
        return_reason field, so existing single-field behavior is preserved;
        clothing/footwear condition fields now also contribute to the severe
        tiers (Fix 1).

        Returns:
            Tuple of (penalty_value, penalty_category, unclassified).
        """
        return_reason = qa_answers.get("return_reason", "").strip().lower()

        # Every field that can carry condition/severity signal.
        severity_field_keys = [
            "return_reason",
            "functional_status",
            "physical_condition",
            "physical_damage",
            "wear_history",
            "washing_history",
            "staining_odour",
            "tag_status",
            "sole_condition",
        ]
        all_fields = [
            qa_answers.get(key, "").strip().lower() for key in severity_field_keys
        ]

        # HIGH penalty (0.35) — non-functional / severely damaged
        for field_val in all_fields:
            if self._matches_any(field_val, HIGH_PENALTY_035):
                return 0.35, "high", False

        # HIGH penalty (0.25) — partially functional / heavy use
        for field_val in all_fields:
            if self._matches_any(field_val, HIGH_PENALTY_025):
                return 0.25, "high", False

        # MEDIUM penalty (0.15) — not-as-described / moderate condition signals
        for field_val in all_fields:
            if self._matches_any(field_val, MEDIUM_PENALTY):
                return 0.15, "medium", False

        # LOW penalty (0.10) — cosmetic / fit / wrong size (reason or physical)
        if self._matches_any(return_reason, LOW_PENALTY_010):
            return 0.10, "low", False

        # LOW penalty (0.05) — preference / changed mind
        if self._matches_any(return_reason, LOW_PENALTY_005):
            return 0.05, "low", False

        # Physical-condition cosmetic fallback
        physical_condition = qa_answers.get("physical_condition", "").strip().lower()
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
