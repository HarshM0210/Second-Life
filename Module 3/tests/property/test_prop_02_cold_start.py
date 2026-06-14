"""
Property Test for Property 2 — Cold-Start Customer Feature Defaults

For any customer_id with zero completed orders in the Customer_Profile store,
the FeatureAssembler SHALL set `user_category_return_rate` to the global category
mean return rate and `in_user_high_return_price_band` to `false`, regardless of
any other input.

**Validates: Requirements 1.4, 2.8**
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from return_prevention.core.feature_assembler import FeatureAssembler
from return_prevention.db.database import Base
from return_prevention.db.repositories import (
    SellerProfileRepository,
    seed_global_seller,
)
from return_prevention.taxonomy.taxonomy_loader import TaxonomyEntry


# ---------------------------------------------------------------------------
# Fixtures & Helpers
# ---------------------------------------------------------------------------

# A known taxonomy fixture with a subcategory keyed by product_id
TAXONOMY_FIXTURE = {
    "test_product": TaxonomyEntry(
        category="Apparel",
        subcategory="Women's Shoes",
        category_return_rate=0.3200,
        has_size_ambiguity=True,
    ),
}


class FakeRequest:
    """Minimal request object for FeatureAssembler.assemble()."""

    def __init__(self, customer_id: str, product_id: str = "test_product"):
        self.customer_id = customer_id
        self.product_id = product_id
        self.page_dwell_seconds = 10.0
        self.is_buy_now = False
        self.seller_id = None
        self.product_price = None
        self.is_sale_active = False


def _make_db_session():
    """Create a fresh in-memory SQLite session with schema and global seller seeded."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()
    seed_global_seller(db=session)
    return session


# ---------------------------------------------------------------------------
# Property Test
# ---------------------------------------------------------------------------


@settings(max_examples=50, deadline=5000)
@given(customer_id=st.text(min_size=1))
@pytest.mark.asyncio
async def test_cold_start_customer_feature_defaults(customer_id: str):
    """
    Property 2: For ANY customer_id with empty order history,
    user_category_return_rate == category_return_rate AND
    in_user_high_return_price_band == False.

    **Validates: Requirements 1.4, 2.8**
    """
    db_session = _make_db_session()

    try:
        request = FakeRequest(customer_id=customer_id)

        with (
            patch(
                "return_prevention.core.feature_assembler.get_taxonomy",
                return_value=TAXONOMY_FIXTURE,
            ),
            patch(
                "return_prevention.integrations.customer_profile.CustomerProfileClient.get",
                new_callable=AsyncMock,
                return_value={"customer_id": customer_id, "order_history": []},
            ),
        ):
            assembler = FeatureAssembler()
            vector, taxonomy_miss = await assembler.assemble(request, db_session)

        # Taxonomy lookup should succeed since product_id maps to fixture
        assert taxonomy_miss is False, (
            f"Taxonomy miss should be False for known product_id, got True "
            f"for customer_id={customer_id!r}"
        )

        # Property assertion: user_category_return_rate (index 1) must equal
        # category_return_rate (index 0) for a cold-start customer
        category_return_rate = TAXONOMY_FIXTURE["test_product"].category_return_rate
        assert vector[0, 1] == pytest.approx(category_return_rate), (
            f"user_category_return_rate should equal category_return_rate "
            f"({category_return_rate}) for cold-start customer_id={customer_id!r}, "
            f"got {vector[0, 1]}"
        )

        # Property assertion: in_user_high_return_price_band (index 2) must be False (0.0)
        assert vector[0, 2] == 0.0, (
            f"in_user_high_return_price_band should be 0.0 (False) for cold-start "
            f"customer_id={customer_id!r}, got {vector[0, 2]}"
        )
    finally:
        db_session.close()
