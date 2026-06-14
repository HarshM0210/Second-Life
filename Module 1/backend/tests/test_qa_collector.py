"""Unit tests for the QA Collector service."""

import pytest

from app.models.qa import Question, ValidationResult
from app.services.qa_collector import (
    QACollector,
    CATEGORY_QUESTIONS,
    FOOD_QUESTIONS,
    ELECTRONICS_QUESTIONS,
    CLOTHING_QUESTIONS,
    OTHER_QUESTIONS,
)


@pytest.fixture
def collector():
    return QACollector()


# ---------------------------------------------------------------------------
# get_questions tests
# ---------------------------------------------------------------------------


class TestGetQuestions:
    """Tests for QACollector.get_questions."""

    def test_food_returns_6_questions(self, collector: QACollector):
        questions = collector.get_questions("Food & Grocery")
        assert len(questions) == 6

    def test_electronics_returns_8_questions(self, collector: QACollector):
        questions = collector.get_questions("Electronics")
        assert len(questions) == 8

    def test_clothing_returns_8_questions(self, collector: QACollector):
        questions = collector.get_questions("Clothing & Footwear")
        assert len(questions) == 8

    def test_other_returns_8_questions(self, collector: QACollector):
        questions = collector.get_questions("Other")
        assert len(questions) == 8

    def test_questions_are_ordered(self, collector: QACollector):
        """Questions should follow the order defined in QnA_Categories.md."""
        food_ids = [q.id for q in collector.get_questions("Food & Grocery")]
        assert food_ids == [
            "return_reason",
            "seal_integrity",
            "packaging_condition",
            "storage_compliance",
            "expiry_date",
            "quantity_remaining",
        ]

        electronics_ids = [q.id for q in collector.get_questions("Electronics")]
        assert electronics_ids == [
            "return_reason",
            "functional_status",
            "physical_condition",
            "accessories",
            "original_packaging",
            "ownership_duration",
            "factory_reset",
            "liquid_damage",
        ]

        clothing_ids = [q.id for q in collector.get_questions("Clothing & Footwear")]
        assert clothing_ids == [
            "return_reason",
            "wear_history",
            "tag_status",
            "washing_history",
            "staining_odour",
            "original_packaging",
            "sole_condition",
            "physical_damage",
        ]

        other_ids = [q.id for q in collector.get_questions("Other")]
        assert other_ids == [
            "return_reason",
            "usage_extent",
            "physical_condition",
            "parts_completeness",
            "original_packaging",
            "skin_contact",
            "safety_concern",
            "hygiene_concerns",
        ]

    def test_unknown_category_raises_value_error(self, collector: QACollector):
        with pytest.raises(ValueError, match="Unknown category"):
            collector.get_questions("Invalid Category")

    def test_returns_question_instances(self, collector: QACollector):
        questions = collector.get_questions("Electronics")
        for q in questions:
            assert isinstance(q, Question)
            assert q.id
            assert q.text
            # Date picker question (Food expiry_date) has empty options; others should have options
            # For Electronics all questions have options
            assert len(q.options) > 0

    def test_food_expiry_date_has_date_picker(self, collector: QACollector):
        questions = collector.get_questions("Food & Grocery")
        expiry_q = next(q for q in questions if q.id == "expiry_date")
        assert expiry_q.supplementary_input is not None
        assert expiry_q.supplementary_input.type == "date_picker"

    def test_electronics_accessories_has_text_field(self, collector: QACollector):
        questions = collector.get_questions("Electronics")
        acc_q = next(q for q in questions if q.id == "accessories")
        assert acc_q.supplementary_input is not None
        assert acc_q.supplementary_input.type == "text_field"
        assert acc_q.supplementary_input.max_length == 200

    def test_clothing_sole_condition_is_conditional(self, collector: QACollector):
        questions = collector.get_questions("Clothing & Footwear")
        sole_q = next(q for q in questions if q.id == "sole_condition")
        assert sole_q.conditional_display == "footwear_only"

    def test_other_safety_concern_has_text_field(self, collector: QACollector):
        questions = collector.get_questions("Other")
        safety_q = next(q for q in questions if q.id == "safety_concern")
        assert safety_q.supplementary_input is not None
        assert safety_q.supplementary_input.type == "text_field"
        assert safety_q.supplementary_input.max_length == 200

    def test_other_parts_completeness_has_text_field(self, collector: QACollector):
        questions = collector.get_questions("Other")
        parts_q = next(q for q in questions if q.id == "parts_completeness")
        assert parts_q.supplementary_input is not None
        assert parts_q.supplementary_input.type == "text_field"
        assert parts_q.supplementary_input.max_length == 200


# ---------------------------------------------------------------------------
# validate_answers tests
# ---------------------------------------------------------------------------


def _full_answers(category: str, collector: QACollector) -> dict[str, str]:
    """Helper to generate a complete answer set for a category."""
    questions = collector.get_questions(category)
    answers = {}
    for q in questions:
        if q.conditional_display is not None:
            continue  # Skip conditional questions
        if q.options:
            answers[q.id] = q.options[0]
        else:
            # For date picker questions, provide a date string
            answers[q.id] = "2025-06-15"
    return answers


class TestValidateAnswers:
    """Tests for QACollector.validate_answers."""

    def test_complete_food_answers_valid(self, collector: QACollector):
        answers = _full_answers("Food & Grocery", collector)
        result = collector.validate_answers("Food & Grocery", answers)
        assert result.is_valid is True
        assert result.missing_question_ids == []

    def test_complete_electronics_answers_valid(self, collector: QACollector):
        answers = _full_answers("Electronics", collector)
        result = collector.validate_answers("Electronics", answers)
        assert result.is_valid is True
        assert result.missing_question_ids == []

    def test_complete_clothing_answers_valid(self, collector: QACollector):
        answers = _full_answers("Clothing & Footwear", collector)
        result = collector.validate_answers("Clothing & Footwear", answers)
        assert result.is_valid is True
        assert result.missing_question_ids == []

    def test_complete_other_answers_valid(self, collector: QACollector):
        answers = _full_answers("Other", collector)
        result = collector.validate_answers("Other", answers)
        assert result.is_valid is True
        assert result.missing_question_ids == []

    def test_missing_single_answer_invalid(self, collector: QACollector):
        answers = _full_answers("Electronics", collector)
        del answers["factory_reset"]
        result = collector.validate_answers("Electronics", answers)
        assert result.is_valid is False
        assert "factory_reset" in result.missing_question_ids

    def test_missing_multiple_answers(self, collector: QACollector):
        answers = _full_answers("Food & Grocery", collector)
        del answers["seal_integrity"]
        del answers["quantity_remaining"]
        result = collector.validate_answers("Food & Grocery", answers)
        assert result.is_valid is False
        assert set(result.missing_question_ids) == {"seal_integrity", "quantity_remaining"}

    def test_empty_string_answer_counted_as_missing(self, collector: QACollector):
        answers = _full_answers("Electronics", collector)
        answers["functional_status"] = ""
        result = collector.validate_answers("Electronics", answers)
        assert result.is_valid is False
        assert "functional_status" in result.missing_question_ids

    def test_whitespace_only_answer_counted_as_missing(self, collector: QACollector):
        answers = _full_answers("Electronics", collector)
        answers["physical_condition"] = "   "
        result = collector.validate_answers("Electronics", answers)
        assert result.is_valid is False
        assert "physical_condition" in result.missing_question_ids

    def test_no_answers_all_missing(self, collector: QACollector):
        result = collector.validate_answers("Food & Grocery", {})
        assert result.is_valid is False
        # Food has 6 questions; 1 has date_picker (expiry_date) with no conditional_display
        # so all 6 are required
        assert len(result.missing_question_ids) == 6

    def test_conditional_question_not_required(self, collector: QACollector):
        """The sole_condition question (footwear_only) should not be required."""
        answers = _full_answers("Clothing & Footwear", collector)
        # sole_condition is conditional and shouldn't be in _full_answers already
        assert "sole_condition" not in answers
        result = collector.validate_answers("Clothing & Footwear", answers)
        assert result.is_valid is True

    def test_conditional_answer_accepted_if_provided(self, collector: QACollector):
        """Providing a conditional answer should not cause validation failure."""
        answers = _full_answers("Clothing & Footwear", collector)
        answers["sole_condition"] = "Completely clean — no sole wear"
        result = collector.validate_answers("Clothing & Footwear", answers)
        assert result.is_valid is True

    def test_unknown_category_raises_value_error(self, collector: QACollector):
        with pytest.raises(ValueError, match="Unknown category"):
            collector.validate_answers("Nonexistent", {"return_reason": "test"})

    def test_returns_validation_result_type(self, collector: QACollector):
        answers = _full_answers("Other", collector)
        result = collector.validate_answers("Other", answers)
        assert isinstance(result, ValidationResult)

    def test_extra_answers_do_not_cause_failure(self, collector: QACollector):
        """Extra keys beyond required questions should be ignored."""
        answers = _full_answers("Food & Grocery", collector)
        answers["extra_field"] = "something"
        result = collector.validate_answers("Food & Grocery", answers)
        assert result.is_valid is True
