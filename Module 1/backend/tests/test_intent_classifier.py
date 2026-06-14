"""
Unit tests for the Intent Classifier service.

Tests keyword mapping, penalty assignment, inconsistency detection,
and fallback behavior per Requirements 8.1, 8.2, 8.3, 8.4, 8.5.
"""

import time

import pytest

from app.models.results import IntentResult
from app.services.intent_classifier import IntentClassifier


@pytest.fixture
def classifier():
    """Provide a fresh IntentClassifier instance."""
    return IntentClassifier()


# ---------------------------------------------------------------------------
# HIGH penalty tests (0.35 — non-functional / completely broken)
# ---------------------------------------------------------------------------


class TestHighPenalty035:
    """Tests for non-functional/completely broken claims → 0.35 penalty."""

    def test_non_functional_electronics(self, classifier):
        qa = {
            "return_reason": "Item is defective / not working",
            "functional_status": "Not functional — does not power on / completely broken",
        }
        result = classifier.classify(qa, "Electronics")
        assert result.return_reason_penalty == 0.35
        assert result.penalty_category == "high"
        assert result.unclassified is False

    def test_severe_physical_damage(self, classifier):
        qa = {
            "return_reason": "Item is defective / not working",
            "physical_condition": "Severe damage (broken screen, crushed, burnt)",
        }
        result = classifier.classify(qa, "Electronics")
        assert result.return_reason_penalty == 0.35
        assert result.penalty_category == "high"

    def test_leaking_or_crushed_food(self, classifier):
        qa = {"return_reason": "Leaking or crushed"}
        result = classifier.classify(qa, "Food & Grocery")
        assert result.return_reason_penalty == 0.35
        assert result.penalty_category == "high"

    def test_significant_damage_clothing(self, classifier):
        qa = {"return_reason": "Significant damage (torn, broken fastening)"}
        result = classifier.classify(qa, "Clothing & Footwear")
        assert result.return_reason_penalty == 0.35
        assert result.penalty_category == "high"


# ---------------------------------------------------------------------------
# HIGH penalty tests (0.25 — partially functional)
# ---------------------------------------------------------------------------


class TestHighPenalty025:
    """Tests for partially functional claims → 0.25 penalty."""

    def test_partially_functional(self, classifier):
        qa = {
            "return_reason": "Item is defective / not working",
            "functional_status": "Partially functional — some features not working",
        }
        result = classifier.classify(qa, "Electronics")
        assert result.return_reason_penalty == 0.25
        assert result.penalty_category == "high"
        assert result.unclassified is False

    def test_defective_not_working_reason(self, classifier):
        qa = {"return_reason": "Item is defective / not working"}
        result = classifier.classify(qa, "Electronics")
        assert result.return_reason_penalty == 0.25
        assert result.penalty_category == "high"

    def test_item_defective_other_category(self, classifier):
        qa = {"return_reason": "Item defective or not working"}
        result = classifier.classify(qa, "Other")
        assert result.return_reason_penalty == 0.25
        assert result.penalty_category == "high"


# ---------------------------------------------------------------------------
# MEDIUM penalty tests (0.15 — not as described)
# ---------------------------------------------------------------------------


class TestMediumPenalty:
    """Tests for 'not as described' claims → 0.15 penalty."""

    def test_not_as_described(self, classifier):
        qa = {"return_reason": "Item not as described in listing"}
        result = classifier.classify(qa, "Electronics")
        assert result.return_reason_penalty == 0.15
        assert result.penalty_category == "medium"
        assert result.unclassified is False

    def test_style_colour_not_as_shown(self, classifier):
        qa = {"return_reason": "Style / colour not as shown in images"}
        result = classifier.classify(qa, "Clothing & Footwear")
        assert result.return_reason_penalty == 0.15
        assert result.penalty_category == "medium"

    def test_quality_not_as_expected(self, classifier):
        qa = {"return_reason": "Quality not as expected (fabric, stitching)"}
        result = classifier.classify(qa, "Clothing & Footwear")
        assert result.return_reason_penalty == 0.15
        assert result.penalty_category == "medium"

    def test_received_wrong_item(self, classifier):
        qa = {"return_reason": "Received wrong item"}
        result = classifier.classify(qa, "Electronics")
        assert result.return_reason_penalty == 0.15
        assert result.penalty_category == "medium"

    def test_wrong_item_delivered_food(self, classifier):
        qa = {"return_reason": "Wrong item delivered"}
        result = classifier.classify(qa, "Food & Grocery")
        assert result.return_reason_penalty == 0.15
        assert result.penalty_category == "medium"

    def test_damaged_on_arrival(self, classifier):
        qa = {"return_reason": "Item damaged on arrival"}
        result = classifier.classify(qa, "Other")
        assert result.return_reason_penalty == 0.15
        assert result.penalty_category == "medium"

    def test_compatibility_issue(self, classifier):
        qa = {"return_reason": "Compatibility issue (wrong model/version)"}
        result = classifier.classify(qa, "Electronics")
        assert result.return_reason_penalty == 0.15
        assert result.penalty_category == "medium"


# ---------------------------------------------------------------------------
# LOW penalty tests (0.05 — preference / changed mind)
# ---------------------------------------------------------------------------


class TestLowPenalty005:
    """Tests for preference reasons → 0.05 penalty."""

    def test_changed_mind(self, classifier):
        qa = {"return_reason": "Changed my mind / no longer needed"}
        result = classifier.classify(qa, "Electronics")
        assert result.return_reason_penalty == 0.05
        assert result.penalty_category == "low"
        assert result.unclassified is False

    def test_changed_mind_clothing(self, classifier):
        qa = {"return_reason": "Changed my mind"}
        result = classifier.classify(qa, "Clothing & Footwear")
        assert result.return_reason_penalty == 0.05
        assert result.penalty_category == "low"


# ---------------------------------------------------------------------------
# LOW penalty tests (0.10 — cosmetic / fit / wrong size)
# ---------------------------------------------------------------------------


class TestLowPenalty010:
    """Tests for cosmetic/fit reasons → 0.10 penalty."""

    def test_wrong_size_too_small(self, classifier):
        qa = {"return_reason": "Wrong size — too small"}
        result = classifier.classify(qa, "Clothing & Footwear")
        assert result.return_reason_penalty == 0.10
        assert result.penalty_category == "low"
        assert result.unclassified is False

    def test_wrong_size_too_large(self, classifier):
        qa = {"return_reason": "Wrong size — too large"}
        result = classifier.classify(qa, "Clothing & Footwear")
        assert result.return_reason_penalty == 0.10
        assert result.penalty_category == "low"

    def test_missing_parts(self, classifier):
        qa = {"return_reason": "Missing parts or accessories"}
        result = classifier.classify(qa, "Other")
        assert result.return_reason_penalty == 0.10
        assert result.penalty_category == "low"


# ---------------------------------------------------------------------------
# Unclassified / fallback tests
# ---------------------------------------------------------------------------


class TestUnclassifiedFallback:
    """Tests for unclassifiable answers → medium (0.15) + unclassified flag."""

    def test_unknown_reason_gets_medium_penalty(self, classifier):
        qa = {"return_reason": "Some completely unknown reason text"}
        result = classifier.classify(qa, "Electronics")
        assert result.return_reason_penalty == 0.15
        assert result.penalty_category == "medium"
        assert result.unclassified is True

    def test_empty_reason_gets_medium_penalty(self, classifier):
        qa = {"return_reason": ""}
        result = classifier.classify(qa, "Electronics")
        assert result.return_reason_penalty == 0.15
        assert result.penalty_category == "medium"
        assert result.unclassified is True

    def test_missing_reason_key_gets_medium_penalty(self, classifier):
        qa = {"some_other_key": "some value"}
        result = classifier.classify(qa, "Electronics")
        assert result.return_reason_penalty == 0.15
        assert result.penalty_category == "medium"
        assert result.unclassified is True

    def test_empty_answers_gets_medium_penalty(self, classifier):
        qa: dict[str, str] = {}
        result = classifier.classify(qa, "Other")
        assert result.return_reason_penalty == 0.15
        assert result.penalty_category == "medium"
        assert result.unclassified is True


# ---------------------------------------------------------------------------
# Inconsistency detection tests (Q&A-to-CV)
# ---------------------------------------------------------------------------


class TestInconsistencyDetection:
    """Tests for check_inconsistencies method (Req 8.4)."""

    def test_never_used_with_wear_detected(self, classifier):
        qa = {"ownership_duration": "Never used — still in original packaging"}
        flags = classifier.check_inconsistencies(qa, wear_detection_penalty=0.3)
        assert "never_used_but_wear_detected" in flags

    def test_never_worn_with_wear_detected(self, classifier):
        qa = {"wear_history": "Never worn — tags still attached"}
        flags = classifier.check_inconsistencies(qa, wear_detection_penalty=0.1)
        assert "never_used_but_wear_detected" in flags

    def test_never_used_completely_unused_with_wear(self, classifier):
        qa = {"usage_extent": "Never used — completely unused"}
        flags = classifier.check_inconsistencies(qa, wear_detection_penalty=0.05)
        assert "never_used_but_wear_detected" in flags

    def test_never_used_no_wear_detected(self, classifier):
        qa = {"ownership_duration": "Never used — still in original packaging"}
        flags = classifier.check_inconsistencies(qa, wear_detection_penalty=0.0)
        assert flags == []

    def test_used_briefly_with_wear_detected(self, classifier):
        qa = {"ownership_duration": "Used briefly (less than a week)"}
        flags = classifier.check_inconsistencies(qa, wear_detection_penalty=0.5)
        assert flags == []

    def test_no_relevant_fields(self, classifier):
        qa = {"return_reason": "Changed my mind"}
        flags = classifier.check_inconsistencies(qa, wear_detection_penalty=0.5)
        assert flags == []

    def test_empty_answers_no_inconsistency(self, classifier):
        qa: dict[str, str] = {}
        flags = classifier.check_inconsistencies(qa, wear_detection_penalty=0.5)
        assert flags == []


# ---------------------------------------------------------------------------
# Response time tests
# ---------------------------------------------------------------------------


class TestPerformance:
    """Tests that classification stays within 200ms budget."""

    def test_classification_under_200ms(self, classifier):
        qa = {
            "return_reason": "Item is defective / not working",
            "functional_status": "Not functional — does not power on / completely broken",
            "physical_condition": "Severe damage (broken screen, crushed, burnt)",
        }
        start = time.perf_counter()
        result = classifier.classify(qa, "Electronics")
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 200, f"Classification took {elapsed_ms:.1f}ms, exceeds 200ms"

    def test_empty_input_under_200ms(self, classifier):
        start = time.perf_counter()
        result = classifier.classify({}, "Other")
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 200, f"Classification took {elapsed_ms:.1f}ms, exceeds 200ms"


# ---------------------------------------------------------------------------
# Result type tests
# ---------------------------------------------------------------------------


class TestResultStructure:
    """Tests that classify returns proper IntentResult instances."""

    def test_returns_intent_result(self, classifier):
        qa = {"return_reason": "Changed my mind"}
        result = classifier.classify(qa, "Electronics")
        assert isinstance(result, IntentResult)

    def test_penalty_in_valid_range(self, classifier):
        qa = {"return_reason": "Item is defective / not working"}
        result = classifier.classify(qa, "Electronics")
        assert 0.05 <= result.return_reason_penalty <= 0.35

    def test_inconsistency_flags_empty_on_classify(self, classifier):
        """classify() returns empty inconsistency_flags (use check_inconsistencies separately)."""
        qa = {"return_reason": "Changed my mind"}
        result = classifier.classify(qa, "Electronics")
        assert result.inconsistency_flags == []

    def test_penalty_category_is_valid_literal(self, classifier):
        qa = {"return_reason": "Changed my mind"}
        result = classifier.classify(qa, "Electronics")
        assert result.penalty_category in ("high", "medium", "low")


# ---------------------------------------------------------------------------
# Clothing condition-field tests (Fix 1 — fields beyond return_reason)
# ---------------------------------------------------------------------------


class TestClothingConditionFields:
    """The classifier must read clothing/footwear condition fields, not just
    return_reason. A benign return_reason ('changed my mind') must NOT mask
    severe condition signals declared in other fields."""

    def test_physical_damage_field_drives_high_penalty(self, classifier):
        # Maya's case: benign reason, but physical_damage is severe.
        qa = {
            "return_reason": "Changed my mind",
            "physical_damage": "Significant damage (torn, broken fastening)",
        }
        result = classifier.classify(qa, "Clothing & Footwear")
        assert result.return_reason_penalty == 0.35
        assert result.penalty_category == "high"

    def test_heavy_wear_fields_drive_025(self, classifier):
        qa = {
            "return_reason": "Changed my mind",
            "wear_history": "Worn multiple times",
            "washing_history": "Yes — washed multiple times",
            "staining_odour": "Yes — visible stain or noticeable odour",
            "tag_status": "All tags removed",
        }
        result = classifier.classify(qa, "Clothing & Footwear")
        assert result.return_reason_penalty == 0.25
        assert result.penalty_category == "high"

    def test_moderate_condition_fields_drive_medium(self, classifier):
        qa = {
            "return_reason": "Changed my mind",
            "tag_status": "Some tags removed",
            "sole_condition": "Visible sole wear or scuffing",
        }
        result = classifier.classify(qa, "Clothing & Footwear")
        assert result.return_reason_penalty == 0.15
        assert result.penalty_category == "medium"

    def test_benign_clothing_stays_low(self, classifier):
        # Priya's case: genuinely near-new — must remain the 0.05 preference tier.
        qa = {
            "return_reason": "Changed my mind",
            "wear_history": "Tried on indoors only — not worn outside",
            "tag_status": "Yes — all tags attached and intact",
            "washing_history": "No — not washed",
            "staining_odour": "No — completely clean",
            "sole_condition": "Completely clean — no sole wear",
            "physical_damage": "No damage",
        }
        result = classifier.classify(qa, "Clothing & Footwear")
        assert result.return_reason_penalty == 0.05
        assert result.penalty_category == "low"
