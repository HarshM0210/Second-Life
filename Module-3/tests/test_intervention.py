"""
tests/test_intervention.py

Unit tests for InterventionGenerator — select_type priority logic,
generate_copy template rendering, and local LLM fallback behavior.

Requirements: 5.2, 6.1–6.4, 6.6
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from return_prevention.core.intervention import InterventionGenerator
from return_prevention.schemas.risk import InterventionType
from return_prevention.taxonomy.taxonomy_loader import TaxonomyEntry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db():
    """A mock SQLAlchemy session."""
    return MagicMock()


@pytest.fixture
def sample_taxonomy() -> dict[str, TaxonomyEntry]:
    """A taxonomy dict with a known subcategory entry."""
    return {
        "Women's Shoes": TaxonomyEntry(
            category="Apparel",
            subcategory="Women's Shoes",
            category_return_rate=0.35,
            has_size_ambiguity=True,
        ),
        "Smartphones": TaxonomyEntry(
            category="Electronics",
            subcategory="Smartphones",
            category_return_rate=0.10,
            has_size_ambiguity=False,
        ),
    }


@pytest.fixture
def fit_profile_repo_with_data():
    """A FitProfileRepository mock that returns count > 0."""
    repo = MagicMock()
    repo.count.return_value = 2
    return repo


@pytest.fixture
def fit_profile_repo_empty():
    """A FitProfileRepository mock that returns count == 0."""
    repo = MagicMock()
    repo.count.return_value = 0
    return repo


# ---------------------------------------------------------------------------
# select_type — Priority order tests
# ---------------------------------------------------------------------------


class TestSelectTypePriority:
    """Test that select_type follows strict priority: SIZE_GUIDANCE > SOCIAL_PROOF > COMPARISON_NUDGE > CLARIFYING_QA."""

    def test_size_guidance_when_fit_profile_has_data(
        self, mock_db, fit_profile_repo_with_data, sample_taxonomy
    ):
        """When SIZE_GUIDANCE condition is met, it's always selected regardless of other conditions."""
        result = InterventionGenerator.select_type(
            customer_id="cust-1",
            brand="Nike",
            subcategory="Women's Shoes",  # present in taxonomy
            category="Apparel",
            fit_profile_repo=fit_profile_repo_with_data,
            taxonomy=sample_taxonomy,
            db=mock_db,
        )
        assert result == InterventionType.SIZE_GUIDANCE

    def test_size_guidance_never_returns_social_proof(
        self, mock_db, fit_profile_repo_with_data, sample_taxonomy
    ):
        """When SIZE_GUIDANCE condition met → never returns SOCIAL_PROOF."""
        result = InterventionGenerator.select_type(
            customer_id="cust-1",
            brand="Nike",
            subcategory="Women's Shoes",
            category="Apparel",
            fit_profile_repo=fit_profile_repo_with_data,
            taxonomy=sample_taxonomy,
            db=mock_db,
        )
        assert result != InterventionType.SOCIAL_PROOF

    def test_size_guidance_never_returns_comparison_nudge(
        self, mock_db, fit_profile_repo_with_data, sample_taxonomy
    ):
        """When SIZE_GUIDANCE condition met → never returns COMPARISON_NUDGE."""
        result = InterventionGenerator.select_type(
            customer_id="cust-1",
            brand="Nike",
            subcategory="Women's Shoes",
            category="Apparel",
            fit_profile_repo=fit_profile_repo_with_data,
            taxonomy=sample_taxonomy,
            db=mock_db,
        )
        assert result != InterventionType.COMPARISON_NUDGE

    def test_size_guidance_never_returns_clarifying_qa(
        self, mock_db, fit_profile_repo_with_data, sample_taxonomy
    ):
        """When SIZE_GUIDANCE condition met → never returns CLARIFYING_QA."""
        result = InterventionGenerator.select_type(
            customer_id="cust-1",
            brand="Nike",
            subcategory="Women's Shoes",
            category="Apparel",
            fit_profile_repo=fit_profile_repo_with_data,
            taxonomy=sample_taxonomy,
            db=mock_db,
        )
        assert result != InterventionType.CLARIFYING_QA

    def test_social_proof_when_no_fit_data_but_taxonomy_has_subcategory(
        self, mock_db, fit_profile_repo_empty, sample_taxonomy
    ):
        """When SIZE_GUIDANCE not met but SOCIAL_PROOF condition met → SOCIAL_PROOF."""
        result = InterventionGenerator.select_type(
            customer_id="cust-1",
            brand="Nike",
            subcategory="Women's Shoes",  # present in taxonomy
            category="Apparel",
            fit_profile_repo=fit_profile_repo_empty,
            taxonomy=sample_taxonomy,
            db=mock_db,
        )
        assert result == InterventionType.SOCIAL_PROOF

    def test_social_proof_never_returns_comparison_nudge(
        self, mock_db, fit_profile_repo_empty, sample_taxonomy
    ):
        """When SOCIAL_PROOF condition met but SIZE_GUIDANCE not → never returns COMPARISON_NUDGE."""
        result = InterventionGenerator.select_type(
            customer_id="cust-1",
            brand="Nike",
            subcategory="Women's Shoes",
            category="Apparel",
            fit_profile_repo=fit_profile_repo_empty,
            taxonomy=sample_taxonomy,
            db=mock_db,
        )
        assert result != InterventionType.COMPARISON_NUDGE

    def test_social_proof_never_returns_clarifying_qa(
        self, mock_db, fit_profile_repo_empty, sample_taxonomy
    ):
        """When SOCIAL_PROOF condition met but SIZE_GUIDANCE not → never returns CLARIFYING_QA."""
        result = InterventionGenerator.select_type(
            customer_id="cust-1",
            brand="Nike",
            subcategory="Women's Shoes",
            category="Apparel",
            fit_profile_repo=fit_profile_repo_empty,
            taxonomy=sample_taxonomy,
            db=mock_db,
        )
        assert result != InterventionType.CLARIFYING_QA

    def test_clarifying_qa_fallback_when_no_conditions_met(
        self, mock_db, fit_profile_repo_empty
    ):
        """CLARIFYING_QA always available when all other conditions are false."""
        # No fit data, subcategory not in taxonomy, no alternative product
        taxonomy = {"Smartphones": TaxonomyEntry(
            category="Electronics",
            subcategory="Smartphones",
            category_return_rate=0.10,
            has_size_ambiguity=False,
        )}

        result = InterventionGenerator.select_type(
            customer_id="cust-1",
            brand="UnknownBrand",
            subcategory="Unknown Subcategory",  # not in taxonomy
            category="Unknown Category",
            fit_profile_repo=fit_profile_repo_empty,
            taxonomy=taxonomy,
            db=mock_db,
        )
        assert result == InterventionType.CLARIFYING_QA

    def test_clarifying_qa_when_taxonomy_is_none(
        self, mock_db, fit_profile_repo_empty
    ):
        """CLARIFYING_QA is selected when taxonomy is None and no fit data."""
        result = InterventionGenerator.select_type(
            customer_id="cust-1",
            brand="SomeBrand",
            subcategory="Anything",
            category="Anything",
            fit_profile_repo=fit_profile_repo_empty,
            taxonomy=None,
            db=mock_db,
        )
        assert result == InterventionType.CLARIFYING_QA

    def test_clarifying_qa_when_taxonomy_empty(
        self, mock_db, fit_profile_repo_empty
    ):
        """CLARIFYING_QA is selected when taxonomy is empty dict and no fit data."""
        result = InterventionGenerator.select_type(
            customer_id="cust-1",
            brand="SomeBrand",
            subcategory="Anything",
            category="Anything",
            fit_profile_repo=fit_profile_repo_empty,
            taxonomy={},
            db=mock_db,
        )
        assert result == InterventionType.CLARIFYING_QA


# ---------------------------------------------------------------------------
# generate_copy — SIZE_GUIDANCE template tests
# ---------------------------------------------------------------------------


class TestGenerateCopySizeGuidance:
    """Test SIZE_GUIDANCE copy generation."""

    def test_full_template_with_3_or_more_orders(self):
        """SIZE_GUIDANCE with >= 3 prior orders uses the full template."""
        context = {
            "brand": "Nike",
            "prior_order_count": 5,
            "kept_size": "M",
            "top_returned_size": "L",
            "current_size": "S",
        }
        copy = InterventionGenerator.generate_copy(
            InterventionType.SIZE_GUIDANCE, context
        )
        assert "your kept size in Nike is M" in copy
        assert "Most returns from Nike are in size L" in copy
        assert "You're about to order size S" in copy

    def test_aggregate_fallback_with_fewer_than_3_orders(self):
        """SIZE_GUIDANCE with < 3 prior orders uses brand-aggregate fallback text."""
        context = {
            "brand": "Adidas",
            "prior_order_count": 2,
            "sizing_tendency": "small",
            "recommended_size": "L",
        }
        copy = InterventionGenerator.generate_copy(
            InterventionType.SIZE_GUIDANCE, context
        )
        assert "Sizing in Adidas runs small" in copy
        assert "Most buyers in your size range keep size L" in copy

    def test_aggregate_fallback_with_zero_orders(self):
        """SIZE_GUIDANCE with 0 prior orders also uses brand-aggregate fallback."""
        context = {
            "brand": "Puma",
            "prior_order_count": 0,
            "sizing_tendency": "true to size",
            "recommended_size": "M",
        }
        copy = InterventionGenerator.generate_copy(
            InterventionType.SIZE_GUIDANCE, context
        )
        assert "Sizing in Puma runs true to size" in copy
        assert "Most buyers in your size range keep size M" in copy


# ---------------------------------------------------------------------------
# generate_copy — SOCIAL_PROOF template tests
# ---------------------------------------------------------------------------


class TestGenerateCopySocialProof:
    """Test SOCIAL_PROOF copy generation."""

    def test_with_top_reason(self):
        """SOCIAL_PROOF includes the return reason when one exists."""
        context = {
            "subcategory": "Women's Shoes",
            "return_rate_pct": 35,
            "top_reason": "wrong size",
        }
        copy = InterventionGenerator.generate_copy(
            InterventionType.SOCIAL_PROOF, context
        )
        assert "35% of buyers in Women's Shoes return items" in copy
        assert "wrong size" in copy

    def test_omits_reason_when_none(self):
        """SOCIAL_PROOF omits return reason when none exists."""
        context = {
            "subcategory": "Smartphones",
            "return_rate_pct": 10,
            "top_reason": None,
        }
        copy = InterventionGenerator.generate_copy(
            InterventionType.SOCIAL_PROOF, context
        )
        assert "10% of buyers in Smartphones return items" in copy
        assert "Make sure this is the right fit for you" in copy
        # Should NOT contain the "most commonly for" phrase
        assert "most commonly for" not in copy

    def test_omits_reason_when_empty_string(self):
        """SOCIAL_PROOF omits reason when it's an empty string."""
        context = {
            "subcategory": "T-Shirts",
            "return_rate_pct": 20,
            "top_reason": "",
        }
        copy = InterventionGenerator.generate_copy(
            InterventionType.SOCIAL_PROOF, context
        )
        assert "Make sure this is the right fit for you" in copy
        assert "most commonly for" not in copy


# ---------------------------------------------------------------------------
# generate_copy — CLARIFYING_QA template tests
# ---------------------------------------------------------------------------


class TestGenerateCopyClarifyingQA:
    """Test CLARIFYING_QA copy generation."""

    def test_alphabetical_tiebreak_equal_frequency(self):
        """Given two equal-frequency reasons, selects the one first alphabetically."""
        # "color mismatch" and "wrong size" each appear once
        context = {
            "subcategory": "T-Shirts",
            "return_reasons": ["wrong size", "color mismatch"],
        }
        copy = InterventionGenerator.generate_copy(
            InterventionType.CLARIFYING_QA, context
        )
        # "color mismatch" < "wrong size" alphabetically
        assert "color mismatch" in copy
        assert "wrong size" not in copy

    def test_alphabetical_tiebreak_multiple_equal(self):
        """With three equal-frequency reasons, picks the first alphabetically."""
        context = {
            "subcategory": "Jeans",
            "return_reasons": ["wrong size", "color mismatch", "bad quality"],
        }
        copy = InterventionGenerator.generate_copy(
            InterventionType.CLARIFYING_QA, context
        )
        assert "bad quality" in copy

    def test_uses_most_frequent_reason_over_alphabetical(self):
        """Frequency takes priority; alphabetical is only the tiebreak."""
        context = {
            "subcategory": "Shoes",
            "return_reasons": ["wrong size", "wrong size", "color mismatch"],
        }
        copy = InterventionGenerator.generate_copy(
            InterventionType.CLARIFYING_QA, context
        )
        # "wrong size" appears twice, "color mismatch" once
        assert "wrong size" in copy

    def test_general_fallback_when_no_reasons(self):
        """Falls back to general Q&A when no return reasons exist."""
        context = {
            "subcategory": "Earphones",
            "return_reasons": None,
        }
        copy = InterventionGenerator.generate_copy(
            InterventionType.CLARIFYING_QA, context
        )
        assert "Not sure this will fit?" in copy
        assert "Check the size guide on this page" in copy

    def test_general_fallback_when_empty_reasons_list(self):
        """Falls back to general Q&A when return_reasons is empty list."""
        context = {
            "subcategory": "Tablets",
            "return_reasons": [],
        }
        copy = InterventionGenerator.generate_copy(
            InterventionType.CLARIFYING_QA, context
        )
        assert "Not sure this will fit?" in copy


# ---------------------------------------------------------------------------
# generate_copy — LLM timeout fallback test
# ---------------------------------------------------------------------------


class TestLLMTimeoutFallback:
    """Test that local LLM timeout falls back to template string without raising."""

    @patch("return_prevention.core.intervention.settings")
    @patch("return_prevention.core.intervention.httpx.Client")
    def test_llm_timeout_falls_back_to_template(self, mock_client_cls, mock_settings):
        """When local LLM times out, generate_copy returns the template string without raising."""
        # Configure settings to have a LOCAL_LLM_URL
        mock_settings.LOCAL_LLM_URL = "http://localhost:11434/api/generate"

        # Mock httpx.Client to raise TimeoutException on post
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.side_effect = httpx.TimeoutException("timed out")
        mock_client_cls.return_value = mock_client

        context = {
            "subcategory": "Women's Shoes",
            "return_rate_pct": 35,
            "top_reason": "wrong size",
        }

        # Should NOT raise
        copy = InterventionGenerator.generate_copy(
            InterventionType.SOCIAL_PROOF, context
        )

        # Should return the template string (not None, not empty)
        assert copy is not None
        assert len(copy) > 0
        assert "35% of buyers in Women's Shoes return items" in copy
        assert "wrong size" in copy

    @patch("return_prevention.core.intervention.settings")
    @patch("return_prevention.core.intervention.httpx.Client")
    def test_llm_generic_error_falls_back_to_template(
        self, mock_client_cls, mock_settings
    ):
        """When local LLM raises a generic error, falls back to template."""
        mock_settings.LOCAL_LLM_URL = "http://localhost:11434/api/generate"

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.side_effect = httpx.ConnectError("connection refused")
        mock_client_cls.return_value = mock_client

        context = {
            "brand": "Nike",
            "prior_order_count": 5,
            "kept_size": "M",
            "top_returned_size": "L",
            "current_size": "S",
        }

        copy = InterventionGenerator.generate_copy(
            InterventionType.SIZE_GUIDANCE, context
        )

        assert copy is not None
        assert "your kept size in Nike is M" in copy

    @patch("return_prevention.core.intervention.settings")
    def test_no_llm_url_uses_template_directly(self, mock_settings):
        """When LOCAL_LLM_URL is None, template is used directly without any HTTP call."""
        mock_settings.LOCAL_LLM_URL = None

        context = {
            "subcategory": "T-Shirts",
            "return_reasons": ["wrong size", "wrong size"],
        }

        copy = InterventionGenerator.generate_copy(
            InterventionType.CLARIFYING_QA, context
        )

        assert "wrong size" in copy
        assert copy is not None
