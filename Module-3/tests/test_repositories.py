"""
Unit tests for return_prevention/db/repositories.py

Tests cover:
- FitProfileRepository: insert → pending status, mark_returned transitions status
  and sets return_reason, unknown order_id returns without mutation,
  mark_kept_bulk only affects rows older than cutoff
- SellerProfileRepository: unknown seller_id returns None, global sentinel seeded
  at startup
- PriceBandProfileRepository: get_high_return_band returns band with highest
  return rate

Requirements: 2.2, 2.3, 2.4, 2.5, 2.7
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from return_prevention.db.database import Base
from return_prevention.db.models import FitProfileRow, PriceBandProfileRow, SellerProfileRow
from return_prevention.db.repositories import (
    GLOBAL_SELLER_ID,
    FitProfileRepository,
    PriceBandProfileRepository,
    SellerProfileRepository,
    seed_global_seller,
)


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


# ---------------------------------------------------------------------------
# FitProfileRepository tests
# ---------------------------------------------------------------------------


class TestFitProfileInsertPending:
    """Test that insert_pending creates a row with status='pending'."""

    def test_insert_creates_row_with_pending_status(self, db_session):
        """insert_pending should create a FitProfileRow with status='pending'."""
        row = FitProfileRepository.insert_pending(
            db=db_session,
            customer_id="cust_001",
            brand="Nike",
            order_id="ORD-100",
            purchased_size="UK 9",
        )

        assert row.id is not None
        assert row.customer_id == "cust_001"
        assert row.brand == "Nike"
        assert row.order_id == "ORD-100"
        assert row.purchased_size == "UK 9"
        assert row.status == "pending"
        assert row.return_reason is None

    def test_insert_pending_persists_to_database(self, db_session):
        """The inserted row should be queryable from the database."""
        FitProfileRepository.insert_pending(
            db=db_session,
            customer_id="cust_002",
            brand="Levi's",
            order_id="ORD-200",
            purchased_size="32",
        )

        rows = db_session.query(FitProfileRow).filter_by(order_id="ORD-200").all()
        assert len(rows) == 1
        assert rows[0].status == "pending"


class TestFitProfileMarkReturned:
    """Test that mark_returned transitions status and sets return_reason."""

    def test_mark_returned_sets_status_and_reason(self, db_session):
        """mark_returned should transition status to 'returned' and set return_reason."""
        FitProfileRepository.insert_pending(
            db=db_session,
            customer_id="cust_001",
            brand="Nike",
            order_id="ORD-300",
            purchased_size="UK 9",
        )

        FitProfileRepository.mark_returned(
            db=db_session,
            order_id="ORD-300",
            return_reason="too large",
        )

        row = db_session.query(FitProfileRow).filter_by(order_id="ORD-300").first()
        assert row.status == "returned"
        assert row.return_reason == "too large"

    def test_mark_returned_with_no_reason(self, db_session):
        """mark_returned without a return_reason should leave it as None."""
        FitProfileRepository.insert_pending(
            db=db_session,
            customer_id="cust_001",
            brand="Nike",
            order_id="ORD-301",
            purchased_size="UK 10",
        )

        FitProfileRepository.mark_returned(
            db=db_session,
            order_id="ORD-301",
            return_reason=None,
        )

        row = db_session.query(FitProfileRow).filter_by(order_id="ORD-301").first()
        assert row.status == "returned"
        assert row.return_reason is None

    def test_mark_returned_unknown_order_id_no_mutation(self, db_session):
        """mark_returned with unknown order_id should not modify any existing rows."""
        # Insert a row first
        FitProfileRepository.insert_pending(
            db=db_session,
            customer_id="cust_001",
            brand="Nike",
            order_id="ORD-400",
            purchased_size="UK 9",
        )

        # Call mark_returned with a non-existent order_id
        FitProfileRepository.mark_returned(
            db=db_session,
            order_id="ORD-NONEXISTENT",
            return_reason="wrong color",
        )

        # Existing row should remain unchanged
        row = db_session.query(FitProfileRow).filter_by(order_id="ORD-400").first()
        assert row.status == "pending"
        assert row.return_reason is None

    def test_mark_returned_unknown_order_id_total_rows_unchanged(self, db_session):
        """mark_returned with unknown order_id should not add or remove any rows."""
        FitProfileRepository.insert_pending(
            db=db_session,
            customer_id="cust_001",
            brand="Nike",
            order_id="ORD-401",
            purchased_size="UK 9",
        )
        FitProfileRepository.insert_pending(
            db=db_session,
            customer_id="cust_002",
            brand="Adidas",
            order_id="ORD-402",
            purchased_size="M",
        )

        count_before = db_session.query(FitProfileRow).count()

        FitProfileRepository.mark_returned(
            db=db_session,
            order_id="ORD-DOES-NOT-EXIST",
            return_reason="defective",
        )

        count_after = db_session.query(FitProfileRow).count()
        assert count_before == count_after


class TestFitProfileMarkKeptBulk:
    """Test that mark_kept_bulk only affects pending rows older than the cutoff."""

    def test_mark_kept_bulk_updates_old_pending_rows(self, db_session):
        """Rows with status='pending' and created_at before cutoff should become 'kept'."""
        # Insert a row and manually set its created_at to 31 days ago
        row = FitProfileRepository.insert_pending(
            db=db_session,
            customer_id="cust_001",
            brand="Nike",
            order_id="ORD-500",
            purchased_size="UK 9",
        )
        old_date = datetime.now(timezone.utc) - timedelta(days=31)
        row.created_at = old_date
        db_session.commit()

        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        count = FitProfileRepository.mark_kept_bulk(db=db_session, cutoff_datetime=cutoff)

        assert count == 1
        db_session.refresh(row)
        assert row.status == "kept"

    def test_mark_kept_bulk_does_not_affect_recent_pending_rows(self, db_session):
        """Rows with created_at after cutoff should remain 'pending'."""
        row = FitProfileRepository.insert_pending(
            db=db_session,
            customer_id="cust_001",
            brand="Nike",
            order_id="ORD-501",
            purchased_size="UK 9",
        )
        # Row was just created (now), so it's recent
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        count = FitProfileRepository.mark_kept_bulk(db=db_session, cutoff_datetime=cutoff)

        assert count == 0
        db_session.refresh(row)
        assert row.status == "pending"

    def test_mark_kept_bulk_does_not_affect_returned_rows(self, db_session):
        """Rows with status='returned' should never be changed by mark_kept_bulk."""
        row = FitProfileRepository.insert_pending(
            db=db_session,
            customer_id="cust_001",
            brand="Nike",
            order_id="ORD-502",
            purchased_size="UK 9",
        )
        # Mark it as returned
        FitProfileRepository.mark_returned(
            db=db_session, order_id="ORD-502", return_reason="defective"
        )
        # Set created_at to 35 days ago (older than cutoff)
        row.created_at = datetime.now(timezone.utc) - timedelta(days=35)
        db_session.commit()

        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        count = FitProfileRepository.mark_kept_bulk(db=db_session, cutoff_datetime=cutoff)

        assert count == 0
        db_session.refresh(row)
        assert row.status == "returned"

    def test_mark_kept_bulk_mixed_rows(self, db_session):
        """Only old pending rows are updated; recent pending and returned are untouched."""
        # Old pending row (should be updated)
        old_pending = FitProfileRepository.insert_pending(
            db=db_session,
            customer_id="cust_001",
            brand="Nike",
            order_id="ORD-600",
            purchased_size="UK 9",
        )
        old_pending.created_at = datetime.now(timezone.utc) - timedelta(days=40)

        # Recent pending row (should NOT be updated)
        recent_pending = FitProfileRepository.insert_pending(
            db=db_session,
            customer_id="cust_001",
            brand="Adidas",
            order_id="ORD-601",
            purchased_size="M",
        )

        # Old returned row (should NOT be updated)
        old_returned = FitProfileRepository.insert_pending(
            db=db_session,
            customer_id="cust_002",
            brand="Puma",
            order_id="ORD-602",
            purchased_size="L",
        )
        FitProfileRepository.mark_returned(
            db=db_session, order_id="ORD-602", return_reason="wrong size"
        )
        old_returned.created_at = datetime.now(timezone.utc) - timedelta(days=45)
        db_session.commit()

        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        count = FitProfileRepository.mark_kept_bulk(db=db_session, cutoff_datetime=cutoff)

        assert count == 1

        db_session.refresh(old_pending)
        db_session.refresh(recent_pending)
        db_session.refresh(old_returned)

        assert old_pending.status == "kept"
        assert recent_pending.status == "pending"
        assert old_returned.status == "returned"


# ---------------------------------------------------------------------------
# SellerProfileRepository tests
# ---------------------------------------------------------------------------


class TestSellerProfileUnknownSeller:
    """Test that get() returns None for unknown seller_id."""

    def test_get_unknown_seller_returns_none(self, db_session):
        """Querying a seller_id that doesn't exist should return None."""
        result = SellerProfileRepository.get(db=db_session, seller_id="unknown_seller")
        assert result is None

    def test_get_unknown_seller_does_not_raise(self, db_session):
        """Querying a non-existent seller should not raise any exception."""
        # This should simply return None without error
        result = SellerProfileRepository.get(db=db_session, seller_id="no-such-seller-999")
        assert result is None


class TestSellerProfileGlobalSentinel:
    """Test that the global sentinel row is seeded at startup."""

    def test_seed_global_seller_creates_sentinel(self, db_session):
        """seed_global_seller should create the __global__ sentinel row."""
        seed_global_seller(db=db_session)

        row = db_session.query(SellerProfileRow).filter_by(
            seller_id=GLOBAL_SELLER_ID
        ).first()

        assert row is not None
        assert row.seller_id == "__global__"
        assert row.return_rate == 0.15
        assert row.total_orders == 0
        assert row.total_returns == 0

    def test_seed_global_seller_is_idempotent(self, db_session):
        """Calling seed_global_seller twice should not create duplicate rows."""
        seed_global_seller(db=db_session)
        seed_global_seller(db=db_session)

        count = (
            db_session.query(SellerProfileRow)
            .filter_by(seller_id=GLOBAL_SELLER_ID)
            .count()
        )
        assert count == 1

    def test_get_global_mean_after_seed(self, db_session):
        """get_global_mean should return the seeded return_rate after seeding."""
        seed_global_seller(db=db_session)
        mean = SellerProfileRepository.get_global_mean(db=db_session)
        assert mean == 0.15

    def test_get_global_mean_without_seed_returns_zero(self, db_session):
        """get_global_mean should return 0.0 if sentinel row is missing."""
        mean = SellerProfileRepository.get_global_mean(db=db_session)
        assert mean == 0.0


# ---------------------------------------------------------------------------
# PriceBandProfileRepository tests
# ---------------------------------------------------------------------------


class TestPriceBandProfileHighReturnBand:
    """Test that get_high_return_band returns the band with highest return rate."""

    def test_returns_band_with_highest_return_rate(self, db_session):
        """get_high_return_band should return the price band with highest return rate."""
        # Insert multiple price bands for the same customer
        PriceBandProfileRepository.upsert(
            db=db_session,
            customer_id="cust_001",
            price_band="0-500",
            total_orders=10,
            total_returns=2,
            return_rate=0.20,
        )
        PriceBandProfileRepository.upsert(
            db=db_session,
            customer_id="cust_001",
            price_band="501-2000",
            total_orders=8,
            total_returns=5,
            return_rate=0.625,
        )
        PriceBandProfileRepository.upsert(
            db=db_session,
            customer_id="cust_001",
            price_band="2001-10000",
            total_orders=5,
            total_returns=1,
            return_rate=0.20,
        )

        result = PriceBandProfileRepository.get_high_return_band(
            db=db_session, customer_id="cust_001"
        )
        assert result == "501-2000"

    def test_returns_none_for_unknown_customer(self, db_session):
        """get_high_return_band should return None if no profile exists for customer."""
        result = PriceBandProfileRepository.get_high_return_band(
            db=db_session, customer_id="nonexistent_customer"
        )
        assert result is None

    def test_single_band_returns_that_band(self, db_session):
        """If the customer has only one band, that band is the highest."""
        PriceBandProfileRepository.upsert(
            db=db_session,
            customer_id="cust_solo",
            price_band="10000+",
            total_orders=3,
            total_returns=2,
            return_rate=0.67,
        )

        result = PriceBandProfileRepository.get_high_return_band(
            db=db_session, customer_id="cust_solo"
        )
        assert result == "10000+"
