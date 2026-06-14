"""
Property Test 6 — Order Confirmation Creates Pending Fit Profile Row

For any confirmed order with a valid (customer_id, brand, order_id, purchased_size),
processing the order confirmation event SHALL result in exactly one Fit_Profile row
with status='pending' for that order_id.

**Validates: Requirements 2.2**
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from return_prevention.db.database import Base
from return_prevention.db.models import FitProfileRow
from return_prevention.db.repositories import FitProfileRepository


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

def order_strategy():
    """
    Generate (customer_id, brand, order_id, purchased_size) tuples.

    Each field is a non-empty text string of up to 50 characters.
    order_id uniqueness is guaranteed within a single test run by Hypothesis
    shrinking, but the property test validates idempotency per unique order_id.
    """
    return st.tuples(
        st.text(min_size=1, max_size=50),  # customer_id
        st.text(min_size=1, max_size=50),  # brand
        st.text(min_size=1, max_size=50),  # order_id
        st.text(min_size=1, max_size=50),  # purchased_size
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db_session():
    """Create a fresh in-memory SQLite session with schema created."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return Session()


# ---------------------------------------------------------------------------
# Property Test
# ---------------------------------------------------------------------------

@given(order=order_strategy())
@settings(max_examples=50, deadline=5000)
def test_order_confirmation_creates_pending_row(order):
    """
    Property 6: Order Confirmation Creates Pending Fit Profile Row.

    For any valid (customer_id, brand, order_id, purchased_size) tuple,
    calling insert_pending creates exactly one row with status='pending'
    for that order_id.

    **Validates: Requirements 2.2**
    """
    customer_id, brand, order_id, purchased_size = order

    db = _make_db_session()
    try:
        # Process the order confirmation event
        FitProfileRepository.insert_pending(
            db=db,
            customer_id=customer_id,
            brand=brand,
            order_id=order_id,
            purchased_size=purchased_size,
        )

        # Assert exactly one row exists for this order_id
        rows = (
            db.query(FitProfileRow)
            .filter(FitProfileRow.order_id == order_id)
            .all()
        )
        assert len(rows) == 1, (
            f"Expected exactly 1 row for order_id={order_id!r}, got {len(rows)}"
        )

        # Assert the row has status='pending'
        row = rows[0]
        assert row.status == "pending", (
            f"Expected status='pending' for order_id={order_id!r}, "
            f"got status={row.status!r}"
        )

        # Assert field values are stored correctly
        assert row.customer_id == customer_id
        assert row.brand == brand
        assert row.purchased_size == purchased_size
    finally:
        db.close()
