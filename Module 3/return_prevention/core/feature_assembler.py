"""
return_prevention/core/feature_assembler.py

Assembles the 9-feature vector for the LightGBM return-risk model.

The assembler collects inputs from four sources (taxonomy, customer profile,
price-band profile, seller profile) plus request-supplied fields, and returns
a numpy array in the exact column order defined by FEATURE_COLS.

This module never raises — it logs warnings and substitutes documented fallbacks
for every missing or failed data source.

Requirements: 1.3, 1.4, 1.5, 1.6, 2.6, 2.7, 2.8, 9.2
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np

from return_prevention.core.model_registry import FEATURE_COLS
from return_prevention.db.repositories import (
    PriceBandProfileRepository,
    SellerProfileRepository,
)
from return_prevention.integrations.customer_profile import CustomerProfileClient
from return_prevention.taxonomy.taxonomy_loader import get_taxonomy

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Price band boundary helpers
# ---------------------------------------------------------------------------

# Band boundaries: label → (lower_inclusive, upper_exclusive)
# Based on design doc:
#   '0-500'      → 0 ≤ price < 500
#   '501-2000'   → 500 ≤ price < 2000
#   '2001-10000' → 2000 ≤ price < 10000
#   '10000+'     → price ≥ 10000
_PRICE_BAND_RANGES: dict[str, tuple[float, float]] = {
    "0-500": (0.0, 500.0),
    "501-2000": (500.0, 2000.0),
    "2001-10000": (2000.0, 10000.0),
    "10000+": (10000.0, float("inf")),
}


def _price_in_band(price: float, band_label: str) -> bool:
    """Check whether a product price falls within the given band."""
    bounds = _PRICE_BAND_RANGES.get(band_label)
    if bounds is None:
        return False
    lower, upper = bounds
    return lower <= price < upper


# ---------------------------------------------------------------------------
# Feature Assembler
# ---------------------------------------------------------------------------


class FeatureAssembler:
    """
    Assembles the 9-feature numpy array for the return-risk model.

    Usage:
        assembler = FeatureAssembler()
        vector, taxonomy_miss = await assembler.assemble(request, db_session)
    """

    def __init__(self) -> None:
        self._customer_client = CustomerProfileClient()

    async def assemble(
        self,
        request: object,
        db_session: "Session",
    ) -> tuple[np.ndarray, bool]:
        """
        Assemble the feature vector from all data sources.

        Returns:
            A tuple of (feature_vector, taxonomy_miss) where feature_vector
            is a numpy array of shape (1, 9) and taxonomy_miss indicates
            whether the product's taxonomy lookup failed.

        This method never raises. On any failure it logs a warning and
        substitutes the documented fallback value.
        """
        try:
            return await self._assemble_impl(request, db_session)
        except Exception as exc:
            logger.error(
                "feature_assembler_unexpected_error error=%s", str(exc)
            )
            # Ultimate fallback: return zeros with taxonomy_miss=True
            return np.zeros((1, 9)), True

    async def _assemble_impl(
        self,
        request: object,
        db_session: "Session",
    ) -> tuple[np.ndarray, bool]:
        """Internal implementation — may raise; caller catches all."""

        # Extract request fields
        product_id: str = getattr(request, "product_id", "")
        customer_id: str = getattr(request, "customer_id", "")
        seller_id: str | None = getattr(request, "seller_id", None)
        product_price: float | None = getattr(request, "product_price", None)
        page_dwell_seconds: float = getattr(request, "page_dwell_seconds", 0.0)
        is_buy_now: bool = getattr(request, "is_buy_now", False)
        is_sale_active: bool = getattr(request, "is_sale_active", False)

        # ──────────────────────────────────────────────────────────────────
        # Step 1: Taxonomy lookup
        # ──────────────────────────────────────────────────────────────────
        taxonomy = get_taxonomy()
        taxonomy_entry = None
        if taxonomy is not None:
            # product_id maps to subcategory key in this prototype
            taxonomy_entry = taxonomy.get(product_id)

        if taxonomy_entry is None:
            # Both category and subcategory absent → short-circuit
            logger.warning(
                "taxonomy_miss product_id=%s — returning short-circuit",
                product_id,
            )
            return np.zeros((1, 9)), True

        category_return_rate: float = taxonomy_entry.category_return_rate
        has_size_ambiguity: bool = taxonomy_entry.has_size_ambiguity
        subcategory: str = taxonomy_entry.subcategory

        # ──────────────────────────────────────────────────────────────────
        # Step 2: Customer profile → user_category_return_rate
        # ──────────────────────────────────────────────────────────────────
        user_category_return_rate = category_return_rate  # default fallback

        try:
            profile_data = await self._customer_client.get(customer_id)
        except Exception as exc:
            logger.warning(
                "customer_profile_fetch_error customer_id=%s error=%s",
                customer_id,
                str(exc),
            )
            profile_data = None

        if profile_data is not None:
            order_history = profile_data.get("order_history", [])
            # Filter orders in the same subcategory
            subcategory_orders = [
                o for o in order_history
                if o.get("subcategory") == subcategory
            ]

            if len(subcategory_orders) >= 2:
                returned_count = sum(
                    1 for o in subcategory_orders
                    if o.get("status") == "returned"
                )
                user_category_return_rate = returned_count / len(subcategory_orders)
            # else: < 2 orders → keep category_return_rate as fallback

        # ──────────────────────────────────────────────────────────────────
        # Step 3: Price band → in_user_high_return_price_band
        # ──────────────────────────────────────────────────────────────────
        in_user_high_return_price_band = False

        try:
            high_return_band = PriceBandProfileRepository.get_high_return_band(
                db_session, customer_id
            )
            if high_return_band is not None and product_price is not None:
                in_user_high_return_price_band = _price_in_band(
                    product_price, high_return_band
                )
        except Exception as exc:
            logger.warning(
                "price_band_lookup_error customer_id=%s error=%s",
                customer_id,
                str(exc),
            )

        # ──────────────────────────────────────────────────────────────────
        # Step 4: Seller profile → seller_return_rate
        # ──────────────────────────────────────────────────────────────────
        seller_return_rate: float = 0.0

        try:
            if seller_id is not None:
                seller_row = SellerProfileRepository.get(db_session, seller_id)
                if seller_row is not None:
                    seller_return_rate = seller_row.return_rate
                else:
                    # Unknown seller → fallback to global mean
                    seller_return_rate = SellerProfileRepository.get_global_mean(
                        db_session
                    )
                    logger.warning(
                        "unknown_seller seller_id=%s — using global mean",
                        seller_id,
                    )
            else:
                # No seller_id provided → use global mean
                seller_return_rate = SellerProfileRepository.get_global_mean(
                    db_session
                )
        except Exception as exc:
            logger.warning(
                "seller_profile_lookup_error seller_id=%s error=%s",
                seller_id,
                str(exc),
            )
            # Fallback: attempt global mean, or 0.0
            try:
                seller_return_rate = SellerProfileRepository.get_global_mean(
                    db_session
                )
            except Exception:
                seller_return_rate = 0.0

        # ──────────────────────────────────────────────────────────────────
        # Steps 5–6: Request-sourced features
        # ──────────────────────────────────────────────────────────────────
        product_review_rating: float = getattr(
            request, "product_review_rating", None
        ) or 3.5

        # ──────────────────────────────────────────────────────────────────
        # Step 7: Assemble numpy array in FEATURE_COLS order
        # ──────────────────────────────────────────────────────────────────
        # FEATURE_COLS order:
        #   0: category_return_rate
        #   1: user_category_return_rate
        #   2: in_user_high_return_price_band
        #   3: has_size_ambiguity
        #   4: page_dwell_seconds
        #   5: is_buy_now
        #   6: product_review_rating
        #   7: seller_return_rate
        #   8: is_sale_active
        feature_vector = np.array([[
            category_return_rate,
            user_category_return_rate,
            float(in_user_high_return_price_band),
            float(has_size_ambiguity),
            page_dwell_seconds,
            float(is_buy_now),
            product_review_rating,
            seller_return_rate,
            float(is_sale_active),
        ]])

        return feature_vector, False
