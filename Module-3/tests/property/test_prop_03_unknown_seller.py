"""
Property Test for Property 3 — Unknown Seller Fallback

For any seller_id absent from the Seller_Profile table, the assembled feature
vector SHALL contain the global mean seller return rate (the __global__ sentinel
value) for the seller_return_rate feature.

**Validates: Requirements 1.5, 2.7**
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import numpy as np
import pytest
from hypothesis import given, settings as hyp_settings
from hypothesis import strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from return_prevention.core.feature_assembler import FeatureAssembler
from return_prevention.db.database import Base
from return_prevention.db.repositories import seed_global_seller
from return_prevention.taxonomy.taxonomy_loader import TaxonomyEntry


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# The global mean return rate seeded by seed_global_seller()
GLOBAL_MEAN_RETURN_RATE = 0.15

# A known subcategory key for the taxonomy fixture
KNOWN_PRODUCT_ID = "prod_test_subcategory"

# The taxonomy fixture with a single known entry
TAXONOMY_FIXTURE: dict[str, TaxonomyEntry] = {
    KNOWN_PRODUCT_ID: TaxonomyEntry(
        category="Apparel",
        subcategory="Women's Shoes",
        category_return_rate=0.3200,
        has_size_ambiguity=True,
    ),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeRequest:
    """Minimal request object for FeatureAssembler."""

    def __init__(self, seller_id: str) -> None:
        self.customer_id = "prop3_customer"
        self.product_id = KNOWN_PRODUCT_ID
        self.page_dwell_seconds = 10.0
        self.is_buy_now = False
        self.seller_id = seller_id
        self.product_price = 1000.0
        self.is_sale_active = False


def _make_db_session():
    """Create a fresh in-memory SQLite session with tables and __global__ seeded."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()
    # Seed only the __global__ sentinel row (return_rate=0.15)
    seed_global_seller(db=session)
    return session


# ---------------------------------------------------------------------------
# Property Test
# ---------------------------------------------------------------------------


class TestProperty03UnknownSellerFallback:
    """
    Property 3: Unknown Seller Fallback

    For any seller_id NOT in the Seller_Profile table, the assembled feature
    vector's seller_return_rate (index 7) must equal the global mean from
    the __global__ sentinel row.

    **Validates: Requirements 1.5, 2.7**
    """

    @hyp_settings(max_examples=50, deadline=5000)
    @given(seller_id=st.text(min_size=1).filter(lambda s: s != "__global__"))
    @pytest.mark.asyncio
    async def test_unknown_seller_uses_global_mean(self, seller_id: str) -> None:
        """
        For any generated seller_id that is not '__global__' (and thus not in
        the DB since we only seed __global__), the feature assembler should
        fall back to the global mean seller return rate.
        """
        db_session = _make_db_session()
        try:
            request = FakeRequest(seller_id=seller_id)

            with (
                patch(
                    "return_prevention.core.feature_assembler.get_taxonomy",
                    return_value=TAXONOMY_FIXTURE,
                ),
                patch(
                    "return_prevention.integrations.customer_profile.CustomerProfileClient.get",
                    new_callable=AsyncMock,
                    return_value=None,
                ),
            ):
                assembler = FeatureAssembler()
                vector, taxonomy_miss = await assembler.assemble(request, db_session)

            # The taxonomy is known, so no short-circuit
            assert taxonomy_miss is False

            # seller_return_rate is at index 7 in FEATURE_COLS
            assert vector[0, 7] == pytest.approx(GLOBAL_MEAN_RETURN_RATE), (
                f"Expected seller_return_rate={GLOBAL_MEAN_RETURN_RATE} for "
                f"unknown seller_id={seller_id!r}, got {vector[0, 7]}"
            )
        finally:
            db_session.close()
