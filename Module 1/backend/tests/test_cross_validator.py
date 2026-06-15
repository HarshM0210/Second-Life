"""
Unit tests for the CrossValidator service.

Tests cross_validate_penalty and escalate_fraud methods.
Validates Requirements: 21.1, 21.2, 21.3, 21.4
"""

import pytest

from app.services.cross_validator import CrossValidator


@pytest.fixture
def validator() -> CrossValidator:
    return CrossValidator()


# ---------------------------------------------------------------------------
# cross_validate_penalty tests
# ---------------------------------------------------------------------------


class TestCrossValidatePenalty:
    """Tests for cross_validate_penalty — uses the more pessimistic signal."""

    def test_qa_penalty_higher(self, validator: CrossValidator) -> None:
        """When QA penalty is higher, it should be returned."""
        result = validator.cross_validate_penalty(qa_penalty=0.35, cv_penalty=0.10)
        assert result == 0.35

    def test_cv_penalty_higher(self, validator: CrossValidator) -> None:
        """When CV penalty is higher, it should be returned."""
        result = validator.cross_validate_penalty(qa_penalty=0.10, cv_penalty=0.45)
        assert result == 0.45

    def test_equal_penalties(self, validator: CrossValidator) -> None:
        """When both penalties are equal, either value is correct."""
        result = validator.cross_validate_penalty(qa_penalty=0.20, cv_penalty=0.20)
        assert result == 0.20

    def test_both_zero(self, validator: CrossValidator) -> None:
        """When both are zero, result should be zero."""
        result = validator.cross_validate_penalty(qa_penalty=0.0, cv_penalty=0.0)
        assert result == 0.0

    def test_both_maximum(self, validator: CrossValidator) -> None:
        """When both are at max (1.0), result should be 1.0."""
        result = validator.cross_validate_penalty(qa_penalty=1.0, cv_penalty=1.0)
        assert result == 1.0

    def test_one_zero_one_nonzero(self, validator: CrossValidator) -> None:
        """When one penalty is zero, the non-zero one is returned."""
        assert validator.cross_validate_penalty(qa_penalty=0.0, cv_penalty=0.25) == 0.25
        assert validator.cross_validate_penalty(qa_penalty=0.15, cv_penalty=0.0) == 0.15


# ---------------------------------------------------------------------------
# escalate_fraud tests
# ---------------------------------------------------------------------------


class TestEscalateFraud:
    """Tests for escalate_fraud — escalation when 'never used' + wear detected."""

    def test_never_used_with_wear_escalates(self, validator: CrossValidator) -> None:
        """When 'never used' and wear_detection_penalty > 0, fraud should escalate."""
        qa_answers = {"wear_history": "Never used — still in original packaging"}
        result = validator.escalate_fraud(
            fraud_confidence=0.20,
            qa_answers=qa_answers,
            wear_detection_penalty=0.50,
        )
        # escalation_factor = 0.10 + (0.50 * 0.30) = 0.25
        assert result == pytest.approx(0.45)

    def test_never_worn_with_wear_escalates(self, validator: CrossValidator) -> None:
        """When 'never worn' and wear detected, fraud should escalate."""
        qa_answers = {"wear_history": "Never worn — tags still attached"}
        result = validator.escalate_fraud(
            fraud_confidence=0.30,
            qa_answers=qa_answers,
            wear_detection_penalty=0.80,
        )
        # escalation_factor = 0.10 + (0.80 * 0.30) = 0.34
        assert result == pytest.approx(0.64)

    def test_never_used_completely_unused(self, validator: CrossValidator) -> None:
        """Indicator 'never used — completely unused' triggers escalation."""
        qa_answers = {"usage_extent": "Never used — completely unused"}
        result = validator.escalate_fraud(
            fraud_confidence=0.10,
            qa_answers=qa_answers,
            wear_detection_penalty=0.30,
        )
        # escalation_factor = 0.10 + (0.30 * 0.30) = 0.19
        assert result == pytest.approx(0.29)

    def test_no_wear_penalty_no_escalation(self, validator: CrossValidator) -> None:
        """When wear_detection_penalty is 0, no escalation regardless of Q&A."""
        qa_answers = {"wear_history": "Never used — still in original packaging"}
        result = validator.escalate_fraud(
            fraud_confidence=0.50,
            qa_answers=qa_answers,
            wear_detection_penalty=0.0,
        )
        assert result == 0.50

    def test_no_never_used_no_escalation(self, validator: CrossValidator) -> None:
        """When Q&A doesn't indicate 'never used', no escalation."""
        qa_answers = {"wear_history": "Used briefly (less than a week)"}
        result = validator.escalate_fraud(
            fraud_confidence=0.40,
            qa_answers=qa_answers,
            wear_detection_penalty=0.60,
        )
        assert result == 0.40

    def test_escalation_capped_at_1(self, validator: CrossValidator) -> None:
        """Fraud confidence should never exceed 1.0."""
        qa_answers = {"wear_history": "Never used — still in original packaging"}
        result = validator.escalate_fraud(
            fraud_confidence=0.85,
            qa_answers=qa_answers,
            wear_detection_penalty=1.0,
        )
        # escalation_factor = 0.10 + (1.0 * 0.30) = 0.40
        # 0.85 + 0.40 = 1.25 → capped at 1.0
        assert result == 1.0

    def test_minimum_escalation_factor(self, validator: CrossValidator) -> None:
        """Even with tiny wear penalty, minimum escalation is 0.10."""
        qa_answers = {"wear_history": "Never used — still in original packaging"}
        result = validator.escalate_fraud(
            fraud_confidence=0.20,
            qa_answers=qa_answers,
            wear_detection_penalty=0.01,
        )
        # escalation_factor = 0.10 + (0.01 * 0.30) = 0.103
        assert result == pytest.approx(0.303)

    def test_maximum_escalation_factor(self, validator: CrossValidator) -> None:
        """With wear_penalty=1.0, max escalation is 0.40."""
        qa_answers = {"wear_history": "Never worn — tags still attached"}
        result = validator.escalate_fraud(
            fraud_confidence=0.0,
            qa_answers=qa_answers,
            wear_detection_penalty=1.0,
        )
        # escalation_factor = 0.10 + (1.0 * 0.30) = 0.40
        assert result == pytest.approx(0.40)

    def test_empty_qa_answers_no_escalation(self, validator: CrossValidator) -> None:
        """Empty Q&A answers should not trigger escalation."""
        result = validator.escalate_fraud(
            fraud_confidence=0.30,
            qa_answers={},
            wear_detection_penalty=0.50,
        )
        assert result == 0.30

    def test_ownership_duration_field_triggers(self, validator: CrossValidator) -> None:
        """'Never used' in ownership_duration field also triggers escalation."""
        qa_answers = {"ownership_duration": "Never used — completely unused"}
        result = validator.escalate_fraud(
            fraud_confidence=0.10,
            qa_answers=qa_answers,
            wear_detection_penalty=0.50,
        )
        # escalation_factor = 0.10 + (0.50 * 0.30) = 0.25
        assert result == pytest.approx(0.35)

    def test_case_insensitive_matching(self, validator: CrossValidator) -> None:
        """Matching should be case-insensitive."""
        qa_answers = {"wear_history": "NEVER USED — STILL IN ORIGINAL PACKAGING"}
        result = validator.escalate_fraud(
            fraud_confidence=0.20,
            qa_answers=qa_answers,
            wear_detection_penalty=0.50,
        )
        # Should escalate because matching is case-insensitive
        # escalation_factor = 0.10 + (0.50 * 0.30) = 0.25
        assert result == pytest.approx(0.45)

    def test_negative_wear_penalty_no_escalation(self, validator: CrossValidator) -> None:
        """Negative wear penalty should not trigger escalation."""
        qa_answers = {"wear_history": "Never used — still in original packaging"}
        result = validator.escalate_fraud(
            fraud_confidence=0.30,
            qa_answers=qa_answers,
            wear_detection_penalty=-0.1,
        )
        assert result == 0.30
