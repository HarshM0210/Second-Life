"""
Cross-Validation service.

Detects inconsistencies between Q&A self-reported answers and CV-detected evidence.
Uses the more pessimistic signal when both Q&A and CV penalties are available.
Escalates fraud_confidence when "never used" claims contradict wear evidence.

Requirements: 21.1, 21.2, 21.3, 21.4
"""

# "Never used" indicators — same as in intent_classifier.py
NEVER_USED_INDICATORS: list[str] = [
    "never used — still in original packaging",
    "never worn — tags still attached",
    "never used — completely unused",
]


class CrossValidator:
    """Cross-validates Q&A answers against CV-detected evidence.

    Ensures the more pessimistic signal is used for health score computation
    and escalates fraud_confidence when self-reporting contradicts physical evidence.
    """

    def cross_validate_penalty(self, qa_penalty: float, cv_penalty: float) -> float:
        """Return the maximum (more pessimistic) penalty.

        When both Q&A-derived penalty and CV-detected penalty are available,
        the authoritative penalty is the higher of the two values — the one
        that reduces the health score more.

        Args:
            qa_penalty: Penalty derived from Q&A intent classification (0.0–1.0).
            cv_penalty: Penalty from anomaly/wear detection (0.0–1.0).

        Returns:
            The maximum of the two penalty values.
        """
        return max(qa_penalty, cv_penalty)

    def escalate_fraud(
        self,
        fraud_confidence: float,
        qa_answers: dict[str, str],
        wear_detection_penalty: float,
    ) -> float:
        """Escalate fraud_confidence when 'never used' contradicts wear evidence.

        If Q&A indicates "never used" AND wear_detection_penalty > 0, the
        fraud_confidence is escalated by a factor proportional to the wear
        penalty, scaled between 0.10 and 0.40.

        Escalation factor = 0.10 + (wear_detection_penalty * 0.30)
        New fraud_confidence = min(1.0, fraud_confidence + escalation_factor)

        Args:
            fraud_confidence: Current fraud confidence score (0.0–1.0).
            qa_answers: Key-value pairs of Q&A responses.
            wear_detection_penalty: Penalty from the Wear Detector (0.0–1.0).

        Returns:
            Updated fraud_confidence (unchanged if conditions not met).
        """
        if wear_detection_penalty <= 0:
            return fraud_confidence

        if not self._indicates_never_used(qa_answers):
            return fraud_confidence

        # Escalation factor proportional to wear_detection_penalty, in [0.10, 0.40]
        escalation_factor = 0.10 + (wear_detection_penalty * 0.30)
        # Clamp escalation factor to the specified range
        escalation_factor = max(0.10, min(0.40, escalation_factor))

        return min(1.0, fraud_confidence + escalation_factor)

    def _indicates_never_used(self, qa_answers: dict[str, str]) -> bool:
        """Check if any Q&A answer indicates 'never used'.

        Checks multiple Q&A fields that could indicate "never used":
        ownership_duration, wear_history, usage_extent.

        Args:
            qa_answers: Key-value pairs of Q&A responses.

        Returns:
            True if any answer matches a "never used" indicator.
        """
        fields_to_check = [
            qa_answers.get("ownership_duration", ""),
            qa_answers.get("wear_history", ""),
            qa_answers.get("usage_extent", ""),
        ]

        for field_value in fields_to_check:
            normalized = field_value.strip().lower()
            if any(indicator in normalized for indicator in NEVER_USED_INDICATORS):
                return True

        return False
