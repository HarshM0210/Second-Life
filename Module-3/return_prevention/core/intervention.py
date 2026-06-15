"""
return_prevention/core/intervention.py

Intervention type selection and copy generation for the PDP banner.

Selection follows strict priority:
  SIZE_GUIDANCE → SOCIAL_PROOF → COMPARISON_NUDGE → CLARIFYING_QA

Copy generation uses template strings with slot-filling. If a local LLM
endpoint is configured (LOCAL_LLM_URL), the template output is optionally
sent for rephrasing with a 500 ms timeout; on timeout or failure the raw
template is returned.

Requirements: 5.1, 5.2, 6.1–6.6
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import TYPE_CHECKING, Optional

import httpx

from return_prevention.config import settings
from return_prevention.schemas.risk import InterventionType
from return_prevention.taxonomy.taxonomy_loader import TaxonomyEntry

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from return_prevention.db.repositories import FitProfileRepository

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Template strings (from design doc)
# ---------------------------------------------------------------------------

# SIZE_GUIDANCE — ≥ 3 prior orders for (customer, brand)
_SIZE_GUIDANCE_FULL = (
    "Heads up: your kept size in {brand} is {kept_size}. "
    "Most returns from {brand} are in size {top_returned_size}. "
    "You're about to order size {current_size}."
)

# SIZE_GUIDANCE — < 3 prior orders (brand-aggregate fallback)
_SIZE_GUIDANCE_AGGREGATE = (
    "Sizing in {brand} runs {sizing_tendency}. "
    "Most buyers in your size range keep size {recommended_size}."
)

# SOCIAL_PROOF — with a known top return reason
_SOCIAL_PROOF_WITH_REASON = (
    "{return_rate_pct}% of buyers in {subcategory} return items — "
    "most commonly for '{top_reason}'. "
    "Double-check before adding to cart."
)

# SOCIAL_PROOF — no known reasons
_SOCIAL_PROOF_NO_REASON = (
    "{return_rate_pct}% of buyers in {subcategory} return items. "
    "Make sure this is the right fit for you."
)

# COMPARISON_NUDGE — alternative found in same subcategory
_COMPARISON_NUDGE_FOUND = (
    "Before you buy: {alt_product_name} has a {alt_return_rate_pct}% return rate "
    "vs {this_return_rate_pct}% for this item. "
    "Both are in {subcategory}."
)

# COMPARISON_NUDGE — no alternative in subcategory → expand to parent category
_COMPARISON_NUDGE_CATEGORY = (
    "Similar items in {category} tend to have lower return rates. "
    "Consider browsing other options before checking out."
)

# CLARIFYING_QA — subcategory-specific reason known
_CLARIFYING_QA_WITH_REASON = (
    'Q: "Why do buyers return {subcategory} items?" '
    "A: \"The most common reason is '{top_reason}'. "
    'If you\'re unsure, check the size guide or seller\'s return policy."'
)

# CLARIFYING_QA — no subcategory reason data → general fallback
_CLARIFYING_QA_GENERAL = (
    'Q: "Not sure this will fit?" '
    'A: "Check the size guide on this page. '
    'Our fit advisor is based on your past orders with this brand."'
)


# ---------------------------------------------------------------------------
# Stub catalog check for COMPARISON_NUDGE
# ---------------------------------------------------------------------------

def _has_alternative_in_subcategory(subcategory: str) -> bool:
    """
    Stub catalog check: returns True if an alternative product exists
    in the given subcategory.

    In production this would query a product catalog service. For the
    prototype, we return False to demonstrate the fallback path unless
    the subcategory is known.
    """
    # Stub: always return False so COMPARISON_NUDGE falls through
    # to CLARIFYING_QA in the prototype. This can be replaced with a
    # real catalog query when the product service is available.
    return False


def _get_alternative_product(subcategory: str) -> Optional[dict]:
    """
    Stub: fetch an alternative product in the same subcategory with a
    lower return rate.

    Returns a dict with keys: alt_product_name, alt_return_rate_pct
    or None if no alternative found.
    """
    # Stub — in production, query the product catalog
    return None


# ---------------------------------------------------------------------------
# InterventionGenerator
# ---------------------------------------------------------------------------


class InterventionGenerator:
    """
    Selects the appropriate intervention type and generates copy for
    the PDP banner.
    """

    @staticmethod
    def select_type(
        customer_id: str,
        brand: str,
        subcategory: str,
        category: str,
        fit_profile_repo: "FitProfileRepository",
        taxonomy: Optional[dict[str, TaxonomyEntry]],
        db: "Session",
    ) -> InterventionType:
        """
        Select the intervention type following strict priority order.

        Priority:
          1. SIZE_GUIDANCE — if fit_profile_repo.count(customer_id, brand) > 0
          2. SOCIAL_PROOF — if subcategory is present in taxonomy
          3. COMPARISON_NUDGE — if alternative product exists in subcategory
          4. CLARIFYING_QA — always available (fallback)

        Args:
            customer_id: The customer identifier.
            brand: The product brand.
            subcategory: The product subcategory.
            category: The product parent category.
            fit_profile_repo: Repository for fit profile queries.
            taxonomy: The loaded category taxonomy dict (keyed by subcategory).
            db: Database session for fit profile queries.

        Returns:
            The selected InterventionType.
        """
        # Priority 1: SIZE_GUIDANCE
        if fit_profile_repo.count(db, customer_id, brand) > 0:
            return InterventionType.SIZE_GUIDANCE

        # Priority 2: SOCIAL_PROOF
        if taxonomy is not None and taxonomy.get(subcategory) is not None:
            return InterventionType.SOCIAL_PROOF

        # Priority 3: COMPARISON_NUDGE
        if _has_alternative_in_subcategory(subcategory):
            return InterventionType.COMPARISON_NUDGE

        # Priority 4: CLARIFYING_QA (always available)
        return InterventionType.CLARIFYING_QA

    @staticmethod
    def generate_copy(
        intervention_type: InterventionType,
        context_dict: dict,
    ) -> str:
        """
        Generate intervention copy by filling template strings.

        If settings.LOCAL_LLM_URL is configured, attempts to rephrase via
        the local LLM with a 500 ms timeout. Falls back to template on
        any failure.

        Args:
            intervention_type: The selected intervention type.
            context_dict: A dict containing the slot values for templates.
                Expected keys vary by intervention_type:

                SIZE_GUIDANCE:
                  - brand (str)
                  - prior_order_count (int) — number of fit profile rows
                  - kept_size (str, optional)
                  - top_returned_size (str, optional)
                  - current_size (str, optional)
                  - sizing_tendency (str, optional) — e.g. "small", "large", "true to size"
                  - recommended_size (str, optional)

                SOCIAL_PROOF:
                  - subcategory (str)
                  - return_rate_pct (int or float)
                  - top_reason (str or None)

                COMPARISON_NUDGE:
                  - subcategory (str)
                  - category (str)
                  - alt_product_name (str or None)
                  - alt_return_rate_pct (float or None)
                  - this_return_rate_pct (float or None)

                CLARIFYING_QA:
                  - subcategory (str)
                  - return_reasons (list[str] or None) — list of reasons
                    from fit profile data

        Returns:
            The generated intervention copy string.
        """
        template_copy = _fill_template(intervention_type, context_dict)

        # Optional local LLM rephrasing
        if settings.LOCAL_LLM_URL:
            rephrased = _rephrase_with_llm(template_copy)
            if rephrased is not None:
                return rephrased

        return template_copy


# ---------------------------------------------------------------------------
# Internal template filling
# ---------------------------------------------------------------------------


def _fill_template(
    intervention_type: InterventionType,
    context: dict,
) -> str:
    """Fill the appropriate template based on intervention type."""

    if intervention_type == InterventionType.SIZE_GUIDANCE:
        return _fill_size_guidance(context)

    if intervention_type == InterventionType.SOCIAL_PROOF:
        return _fill_social_proof(context)

    if intervention_type == InterventionType.COMPARISON_NUDGE:
        return _fill_comparison_nudge(context)

    # CLARIFYING_QA
    return _fill_clarifying_qa(context)


def _fill_size_guidance(context: dict) -> str:
    """
    SIZE_GUIDANCE template.

    Uses full template if ≥ 3 prior orders; otherwise brand-aggregate fallback.
    """
    brand = context.get("brand", "this brand")
    prior_order_count = context.get("prior_order_count", 0)

    if prior_order_count >= 3:
        kept_size = context.get("kept_size", "M")
        top_returned_size = context.get("top_returned_size", "L")
        current_size = context.get("current_size", "M")
        return _SIZE_GUIDANCE_FULL.format(
            brand=brand,
            kept_size=kept_size,
            top_returned_size=top_returned_size,
            current_size=current_size,
        )
    else:
        sizing_tendency = context.get("sizing_tendency", "true to size")
        recommended_size = context.get("recommended_size", "M")
        return _SIZE_GUIDANCE_AGGREGATE.format(
            brand=brand,
            sizing_tendency=sizing_tendency,
            recommended_size=recommended_size,
        )


def _fill_social_proof(context: dict) -> str:
    """
    SOCIAL_PROOF template.

    Includes return reason phrase if one exists; omits it otherwise.
    """
    subcategory = context.get("subcategory", "this category")
    return_rate_pct = context.get("return_rate_pct", 0)
    top_reason = context.get("top_reason")

    if top_reason:
        return _SOCIAL_PROOF_WITH_REASON.format(
            return_rate_pct=return_rate_pct,
            subcategory=subcategory,
            top_reason=top_reason,
        )
    else:
        return _SOCIAL_PROOF_NO_REASON.format(
            return_rate_pct=return_rate_pct,
            subcategory=subcategory,
        )


def _fill_comparison_nudge(context: dict) -> str:
    """
    COMPARISON_NUDGE template.

    Uses alternative product info if found; expands to parent category otherwise.
    """
    alt_product_name = context.get("alt_product_name")
    subcategory = context.get("subcategory", "this subcategory")
    category = context.get("category", "this category")

    if alt_product_name:
        alt_return_rate_pct = context.get("alt_return_rate_pct", 0)
        this_return_rate_pct = context.get("this_return_rate_pct", 0)
        return _COMPARISON_NUDGE_FOUND.format(
            alt_product_name=alt_product_name,
            alt_return_rate_pct=alt_return_rate_pct,
            this_return_rate_pct=this_return_rate_pct,
            subcategory=subcategory,
        )
    else:
        return _COMPARISON_NUDGE_CATEGORY.format(category=category)


def _fill_clarifying_qa(context: dict) -> str:
    """
    CLARIFYING_QA template.

    Uses the top return reason for the subcategory. If multiple reasons share
    the highest frequency, selects the one that appears first alphabetically.
    Falls back to general Q&A if no reasons exist.
    """
    subcategory = context.get("subcategory", "this category")
    return_reasons: Optional[list[str]] = context.get("return_reasons")

    if not return_reasons:
        return _CLARIFYING_QA_GENERAL

    # Count frequencies and find the top reason with alphabetical tiebreak
    top_reason = _get_top_reason_alphabetical(return_reasons)

    if top_reason is None:
        return _CLARIFYING_QA_GENERAL

    return _CLARIFYING_QA_WITH_REASON.format(
        subcategory=subcategory,
        top_reason=top_reason,
    )


def _get_top_reason_alphabetical(reasons: list[str]) -> Optional[str]:
    """
    Find the most frequent reason. If multiple reasons share the highest
    frequency, return the one that comes first alphabetically.
    """
    if not reasons:
        return None

    counts = Counter(reasons)
    max_count = max(counts.values())

    # Get all reasons with the max count
    top_reasons = [reason for reason, count in counts.items() if count == max_count]

    # Alphabetical tiebreak
    top_reasons.sort()
    return top_reasons[0]


# ---------------------------------------------------------------------------
# Local LLM rephrasing (optional)
# ---------------------------------------------------------------------------


def _rephrase_with_llm(template_copy: str) -> Optional[str]:
    """
    POST template copy to the local LLM for rephrasing.

    Uses a 500 ms timeout. Returns None on timeout or any failure,
    allowing the caller to fall back to the raw template.
    """
    if not settings.LOCAL_LLM_URL:
        return None

    try:
        with httpx.Client(timeout=0.5) as client:
            response = client.post(
                settings.LOCAL_LLM_URL,
                json={
                    "prompt": (
                        "Rephrase the following intervention copy for a "
                        "product page banner. Preserve all factual data points "
                        "(sizes, percentages, product names). Keep it concise "
                        "and friendly:\n\n"
                        f"{template_copy}"
                    ),
                },
            )
            if response.status_code == 200:
                data = response.json()
                rephrased = data.get("text") or data.get("response")
                if rephrased and isinstance(rephrased, str) and rephrased.strip():
                    return rephrased.strip()
    except httpx.TimeoutException:
        logger.warning(
            "local_llm_timeout url=%s — falling back to template",
            settings.LOCAL_LLM_URL,
        )
    except Exception as exc:
        logger.warning(
            "local_llm_error url=%s error=%s — falling back to template",
            settings.LOCAL_LLM_URL,
            str(exc),
        )

    return None
