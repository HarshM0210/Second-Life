"""
Property Test 12 — Intervention Selection Follows Priority Order

For all boolean combinations of (has_fit_data, has_taxonomy_data, has_alternative),
the InterventionGenerator.select_type SHALL return the highest-priority type whose
condition is True.

Priority: SIZE_GUIDANCE > SOCIAL_PROOF > COMPARISON_NUDGE > CLARIFYING_QA

**Validates: Requirements 5.1, 5.2**
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from hypothesis import given, settings as h_settings
from hypothesis import strategies as st

from return_prevention.core.intervention import InterventionGenerator
from return_prevention.schemas.risk import InterventionType
from return_prevention.taxonomy.taxonomy_loader import TaxonomyEntry


def intervention_condition_strategy():
    """
    Generate all boolean combinations of:
      - has_fit_data: whether FitProfileRepository.count() > 0
      - has_taxonomy_data: whether taxonomy contains the subcategory
      - has_alternative: whether _has_alternative_in_subcategory returns True
    """
    return st.tuples(st.booleans(), st.booleans(), st.booleans())


@given(conditions=intervention_condition_strategy())
@h_settings(max_examples=50, deadline=10000)
def test_intervention_priority_order(conditions):
    """
    Property 12: Intervention Selection Follows Priority Order.

    For each boolean combination of conditions, assert the selected type
    is the highest-priority type whose condition is True.

    Priority: SIZE_GUIDANCE > SOCIAL_PROOF > COMPARISON_NUDGE > CLARIFYING_QA

    **Validates: Requirements 5.1, 5.2**
    """
    has_fit_data, has_taxonomy_data, has_alternative = conditions

    # Setup mocks
    mock_db = MagicMock()
    mock_fit_repo = MagicMock()
    mock_fit_repo.count = MagicMock(return_value=1 if has_fit_data else 0)

    # Build taxonomy: if has_taxonomy_data, include the subcategory
    subcategory = "test_subcategory"
    if has_taxonomy_data:
        taxonomy = {
            subcategory: TaxonomyEntry(
                category="TestCategory",
                subcategory=subcategory,
                category_return_rate=0.25,
                has_size_ambiguity=False,
            )
        }
    else:
        taxonomy = {}

    # Mock _has_alternative_in_subcategory
    with patch(
        "return_prevention.core.intervention._has_alternative_in_subcategory",
        return_value=has_alternative,
    ):
        result = InterventionGenerator.select_type(
            customer_id="cust_123",
            brand="TestBrand",
            subcategory=subcategory,
            category="TestCategory",
            fit_profile_repo=mock_fit_repo,
            taxonomy=taxonomy,
            db=mock_db,
        )

    # Determine expected result based on priority
    if has_fit_data:
        expected = InterventionType.SIZE_GUIDANCE
    elif has_taxonomy_data:
        expected = InterventionType.SOCIAL_PROOF
    elif has_alternative:
        expected = InterventionType.COMPARISON_NUDGE
    else:
        expected = InterventionType.CLARIFYING_QA

    assert result == expected, (
        f"Expected {expected.value} for conditions "
        f"(has_fit_data={has_fit_data}, has_taxonomy_data={has_taxonomy_data}, "
        f"has_alternative={has_alternative}), but got {result.value}"
    )
