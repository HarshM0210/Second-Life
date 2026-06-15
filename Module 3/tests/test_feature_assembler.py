"""
Unit tests for return_prevention/core/feature_assembler.py

Tests cover:
- Cold-start customer (empty history): user_category_return_rate == category_return_rate
  and in_user_high_return_price_band == False
- Unknown seller: seller_return_rate == global_mean
- CustomerProfileClient returns None: feature vector uses category-level baselines,
  no exception raised
- Taxonomy miss for both category and subcategory: short-circuit with taxonomy_miss=True
- Column order matches FEATURE_COLS constant exactly

Requirements: 1.4, 1.5, 1.6, 2.8
"""

from unittest.mock import AsyncMock, patch

import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from return_prevention.core.feature_assembler import FeatureAssembler
from return_prevention.core.model_registry import FEATURE_COLS
from return_prevention.db.database import Base
from return_prevention.db.repositories import (
    SellerProfileRepository,
    seed_global_seller,
)
from return_prevention.taxonomy.taxonomy_loader import TaxonomyEntry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database and yield a session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def sample_taxonomy():
    """A minimal taxonomy dict with one entry for testing."""
    return {
        "prod_shoes_001": TaxonomyEntry(
            category="Apparel",
            subcategory="Women's Shoes",
            category_return_rate=0.3200,
            has_size_ambiguity=True,
        ),
        "prod_phone_001": TaxonomyEntry(
            category="Electronics",
            subcategory="Smartphones",
            category_return_rate=0.0800,
            has_size_ambiguity=False,
        ),
    }


class FakeRequest:
    """Minimal mock of RiskScoreRequest for testing."""

    def __init__(
        self,
        customer_id: str = "cust_001",
        product_id: str = "prod_shoes_001",
        page_dwell_seconds: float = 15.0,
        is_buy_now: bool = False,
        seller_id: str | None = "seller_A",
        product_price: float | None = 1500.0,
        is_sale_active: bool = False,
    ):
        self.customer_id = customer_id
        self.product_id = product_id
        self.page_dwell_seconds = page_dwell_seconds
        self.is_buy_now = is_buy_now
        self.seller_id = seller_id
        self.product_price = product_price
        self.is_sale_active = is_sale_active


# ---------------------------------------------------------------------------
# Tests: Cold-start customer (empty history)
# ---------------------------------------------------------------------------


class TestColdStartCustomer:
    """
    Cold-start customer (empty order history):
    - user_category_return_rate should equal category_return_rate
    - in_user_high_return_price_band should be False
    """

    @pytest.mark.asyncio
    async def test_empty_history_user_rate_equals_category_rate(
        self, db_session, sample_taxonomy
    ):
        """
        When CustomerProfileClient returns a profile with an empty order_history,
        user_category_return_rate should fall back to category_return_rate.
        """
        seed_global_seller(db=db_session)
        # Seed the seller so it doesn't fall back to global mean
        SellerProfileRepository.upsert(
            db=db_session,
            seller_id="seller_A",
            return_rate=0.10,
            total_orders=100,
            total_returns=10,
        )

        request = FakeRequest(customer_id="new_customer", product_id="prod_shoes_001")

        # Mock get_taxonomy to return our fixture
        # Mock CustomerProfileClient.get to return profile with empty history
        with (
            patch(
                "return_prevention.core.feature_assembler.get_taxonomy",
                return_value=sample_taxonomy,
            ),
            patch(
                "return_prevention.integrations.customer_profile.CustomerProfileClient.get",
                new_callable=AsyncMock,
                return_value={"customer_id": "new_customer", "order_history": []},
            ),
        ):
            assembler = FeatureAssembler()
            vector, taxonomy_miss = await assembler.assemble(request, db_session)

        assert taxonomy_miss is False
        # user_category_return_rate (index 1) == category_return_rate (index 0)
        assert vector[0, 1] == pytest.approx(0.3200)
        assert vector[0, 0] == pytest.approx(0.3200)
        # in_user_high_return_price_band (index 2) should be False (0.0)
        assert vector[0, 2] == 0.0

    @pytest.mark.asyncio
    async def test_fewer_than_two_orders_uses_category_rate(
        self, db_session, sample_taxonomy
    ):
        """
        When a customer has fewer than 2 orders in the subcategory,
        user_category_return_rate should fall back to category_return_rate.
        """
        seed_global_seller(db=db_session)
        SellerProfileRepository.upsert(
            db=db_session,
            seller_id="seller_A",
            return_rate=0.10,
            total_orders=100,
            total_returns=10,
        )

        request = FakeRequest(customer_id="cust_few_orders", product_id="prod_shoes_001")

        # Profile with only 1 order in the same subcategory
        profile_data = {
            "customer_id": "cust_few_orders",
            "order_history": [
                {
                    "order_id": "ORD-001",
                    "product_id": "prod_shoes_001",
                    "category": "Apparel",
                    "subcategory": "Women's Shoes",
                    "brand": "Nike",
                    "purchased_size": "UK 6",
                    "price": 1200.0,
                    "seller_id": "seller_A",
                    "status": "returned",
                    "return_reason": "too small",
                    "order_date": "2025-01-01T10:00:00Z",
                }
            ],
        }

        with (
            patch(
                "return_prevention.core.feature_assembler.get_taxonomy",
                return_value=sample_taxonomy,
            ),
            patch(
                "return_prevention.integrations.customer_profile.CustomerProfileClient.get",
                new_callable=AsyncMock,
                return_value=profile_data,
            ),
        ):
            assembler = FeatureAssembler()
            vector, taxonomy_miss = await assembler.assemble(request, db_session)

        # With < 2 orders in subcategory, falls back to category_return_rate
        assert vector[0, 1] == pytest.approx(0.3200)


# ---------------------------------------------------------------------------
# Tests: Unknown seller → seller_return_rate == global_mean
# ---------------------------------------------------------------------------


class TestUnknownSeller:
    """
    When a seller_id is not in the SellerProfile table,
    seller_return_rate should equal the global mean from the __global__ sentinel row.
    """

    @pytest.mark.asyncio
    async def test_unknown_seller_uses_global_mean(self, db_session, sample_taxonomy):
        """
        seller_return_rate should be the __global__ sentinel return_rate
        when seller_id is not found.
        """
        seed_global_seller(db=db_session)
        # Global sentinel has return_rate = 0.15

        request = FakeRequest(
            customer_id="cust_001",
            product_id="prod_shoes_001",
            seller_id="unknown_seller_xyz",
        )

        with (
            patch(
                "return_prevention.core.feature_assembler.get_taxonomy",
                return_value=sample_taxonomy,
            ),
            patch(
                "return_prevention.integrations.customer_profile.CustomerProfileClient.get",
                new_callable=AsyncMock,
                return_value={"customer_id": "cust_001", "order_history": []},
            ),
        ):
            assembler = FeatureAssembler()
            vector, taxonomy_miss = await assembler.assemble(request, db_session)

        assert taxonomy_miss is False
        # seller_return_rate is at index 7 in FEATURE_COLS
        assert vector[0, 7] == pytest.approx(0.15)


# ---------------------------------------------------------------------------
# Tests: CustomerProfileClient returns None
# ---------------------------------------------------------------------------


class TestCustomerProfileClientReturnsNone:
    """
    When CustomerProfileClient.get() returns None (timeout/error),
    the feature vector should use category-level baselines and no exception
    should be raised.
    """

    @pytest.mark.asyncio
    async def test_none_profile_uses_category_baselines(
        self, db_session, sample_taxonomy
    ):
        """
        user_category_return_rate should equal category_return_rate and
        in_user_high_return_price_band should be False when client returns None.
        """
        seed_global_seller(db=db_session)
        SellerProfileRepository.upsert(
            db=db_session,
            seller_id="seller_A",
            return_rate=0.10,
            total_orders=100,
            total_returns=10,
        )

        request = FakeRequest(customer_id="cust_timeout", product_id="prod_shoes_001")

        with (
            patch(
                "return_prevention.core.feature_assembler.get_taxonomy",
                return_value=sample_taxonomy,
            ),
            patch(
                "return_prevention.integrations.customer_profile.CustomerProfileClient.get",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            assembler = FeatureAssembler()
            vector, taxonomy_miss = await assembler.assemble(request, db_session)

        # No exception raised — taxonomy_miss is False
        assert taxonomy_miss is False
        # user_category_return_rate (index 1) == category_return_rate (index 0)
        assert vector[0, 1] == pytest.approx(0.3200)
        assert vector[0, 0] == pytest.approx(0.3200)
        # in_user_high_return_price_band (index 2) == False (no price band profile)
        assert vector[0, 2] == 0.0

    @pytest.mark.asyncio
    async def test_none_profile_does_not_raise(self, db_session, sample_taxonomy):
        """Calling assemble with None client response should not raise any exception."""
        seed_global_seller(db=db_session)
        SellerProfileRepository.upsert(
            db=db_session,
            seller_id="seller_A",
            return_rate=0.10,
            total_orders=100,
            total_returns=10,
        )

        request = FakeRequest(customer_id="cust_err", product_id="prod_shoes_001")

        with (
            patch(
                "return_prevention.core.feature_assembler.get_taxonomy",
                return_value=sample_taxonomy,
            ),
            patch(
                "return_prevention.integrations.customer_profile.CustomerProfileClient.get",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            assembler = FeatureAssembler()
            # Should not raise
            vector, taxonomy_miss = await assembler.assemble(request, db_session)

        assert vector.shape == (1, 9)


# ---------------------------------------------------------------------------
# Tests: Taxonomy miss (product_id not in taxonomy)
# ---------------------------------------------------------------------------


class TestTaxonomyMiss:
    """
    When the product_id is not found in the taxonomy (both category and
    subcategory absent), the assembler should short-circuit with
    taxonomy_miss=True.
    """

    @pytest.mark.asyncio
    async def test_unknown_product_returns_taxonomy_miss_true(
        self, db_session, sample_taxonomy
    ):
        """
        If product_id doesn't exist in taxonomy, return taxonomy_miss=True
        and a zero vector.
        """
        seed_global_seller(db=db_session)

        request = FakeRequest(
            customer_id="cust_001",
            product_id="completely_unknown_product",
        )

        with (
            patch(
                "return_prevention.core.feature_assembler.get_taxonomy",
                return_value=sample_taxonomy,
            ),
            patch(
                "return_prevention.integrations.customer_profile.CustomerProfileClient.get",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            assembler = FeatureAssembler()
            vector, taxonomy_miss = await assembler.assemble(request, db_session)

        assert taxonomy_miss is True
        # Vector should be zeros on short-circuit
        np.testing.assert_array_equal(vector, np.zeros((1, 9)))

    @pytest.mark.asyncio
    async def test_empty_taxonomy_returns_taxonomy_miss(self, db_session):
        """
        If taxonomy is an empty dict, any product_id should be a taxonomy miss.
        """
        seed_global_seller(db=db_session)

        request = FakeRequest(
            customer_id="cust_001",
            product_id="prod_shoes_001",
        )

        with (
            patch(
                "return_prevention.core.feature_assembler.get_taxonomy",
                return_value={},
            ),
            patch(
                "return_prevention.integrations.customer_profile.CustomerProfileClient.get",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            assembler = FeatureAssembler()
            vector, taxonomy_miss = await assembler.assemble(request, db_session)

        assert taxonomy_miss is True


# ---------------------------------------------------------------------------
# Tests: Column order matches FEATURE_COLS constant exactly
# ---------------------------------------------------------------------------


class TestColumnOrder:
    """
    The feature vector column order must match FEATURE_COLS exactly:
    [category_return_rate, user_category_return_rate, in_user_high_return_price_band,
     has_size_ambiguity, page_dwell_seconds, is_buy_now, product_review_rating,
     seller_return_rate, is_sale_active]
    """

    @pytest.mark.asyncio
    async def test_feature_vector_column_order(self, db_session, sample_taxonomy):
        """
        Assemble a vector with known values at each position and verify
        each column matches the expected FEATURE_COLS index.
        """
        seed_global_seller(db=db_session)
        SellerProfileRepository.upsert(
            db=db_session,
            seller_id="seller_A",
            return_rate=0.22,
            total_orders=50,
            total_returns=11,
        )

        # Use an Electronics product (has_size_ambiguity=False)
        request = FakeRequest(
            customer_id="cust_col_order",
            product_id="prod_phone_001",
            page_dwell_seconds=42.5,
            is_buy_now=True,
            seller_id="seller_A",
            product_price=800.0,
            is_sale_active=True,
        )

        with (
            patch(
                "return_prevention.core.feature_assembler.get_taxonomy",
                return_value=sample_taxonomy,
            ),
            patch(
                "return_prevention.integrations.customer_profile.CustomerProfileClient.get",
                new_callable=AsyncMock,
                return_value={"customer_id": "cust_col_order", "order_history": []},
            ),
        ):
            assembler = FeatureAssembler()
            vector, taxonomy_miss = await assembler.assemble(request, db_session)

        assert taxonomy_miss is False
        assert vector.shape == (1, 9)

        # Verify FEATURE_COLS has exactly 9 entries
        assert len(FEATURE_COLS) == 9

        # Index 0: category_return_rate (Smartphones = 0.08)
        assert FEATURE_COLS[0] == "category_return_rate"
        assert vector[0, 0] == pytest.approx(0.0800)

        # Index 1: user_category_return_rate (cold-start → category_return_rate)
        assert FEATURE_COLS[1] == "user_category_return_rate"
        assert vector[0, 1] == pytest.approx(0.0800)

        # Index 2: in_user_high_return_price_band (no price band profile → False)
        assert FEATURE_COLS[2] == "in_user_high_return_price_band"
        assert vector[0, 2] == 0.0

        # Index 3: has_size_ambiguity (Smartphones = False)
        assert FEATURE_COLS[3] == "has_size_ambiguity"
        assert vector[0, 3] == 0.0

        # Index 4: page_dwell_seconds = 42.5
        assert FEATURE_COLS[4] == "page_dwell_seconds"
        assert vector[0, 4] == pytest.approx(42.5)

        # Index 5: is_buy_now = True
        assert FEATURE_COLS[5] == "is_buy_now"
        assert vector[0, 5] == 1.0

        # Index 6: product_review_rating (fallback 3.5 since not on request)
        assert FEATURE_COLS[6] == "product_review_rating"
        assert vector[0, 6] == pytest.approx(3.5)

        # Index 7: seller_return_rate = 0.22
        assert FEATURE_COLS[7] == "seller_return_rate"
        assert vector[0, 7] == pytest.approx(0.22)

        # Index 8: is_sale_active = True
        assert FEATURE_COLS[8] == "is_sale_active"
        assert vector[0, 8] == 1.0
