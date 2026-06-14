"""
Property Test 7 — Return Event Transitions Status and Preserves Data

For any return event referencing an existing order_id in the Fit_Profile table,
processing the event SHALL transition the row to status='returned', and the
return_reason field SHALL contain the provided reason (or remain null if none
was provided). The total number of rows in the table SHALL be unchanged.

**Validates: Requirements 2.3**
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

def existing_order_strategy():
    """
    Generate test data: order fields + optional return reason.

    Returns (customer_id, brand, order_id, purchased_size, return_reason)
    where return_reason is either a non-empty string or None.
    """
    return st.tuples(
        st.text(min_size=1, max_size=50),  # customer_id
        st.text(min_size=1, max_size=50),  # brand
        st.text(min_size=1, max_size=50),  # order_id
        st.text(min_size=1, max_size=50),  # purchased_size
        st.one_of(st.none(), st.text(min_size=1, max_size=100)),  # return_reason
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

@given(data=existing_order_strategy())
@settings(max_examples=50, deadline=5000)
def test_return_event_transitions_status_and_preserves_row_count(data):
    """
    Property 7: Return Event Transitions Status and Preserves Data.

    For any return event on an existing order_id:
    - status transitions to 'returned'
    - return_reason matches the provided value (or None)
    - total row count in the table is unchanged

    **Validates: Requirements 2.3**
    """
    customer_id, brand, order_id, purchased_size, return_reason = data

    db = _make_db_session()
    try:
        # Pre-seed the order as pending
        FitProfileRepository.insert_pending(
            db=db,
            customer_id=customer_id,
            brand=brand,
            order_id=order_id,
            purchased_size=purchased_size,
        )

        # Record total row count before the return event
        row_count_before = db.query(FitProfileRow).count()

        # Process the return event
        FitProfileRepository.mark_returned(
            db=db,
            order_id=order_id,
            return_reason=return_reason,
        )

        # Assert status is now 'returned'
        row = (
            db.query(FitProfileRow)
            .filter(FitProfileRow.order_id == order_id)
            .first()
        )
        assert row is not None, f"Row for order_id={order_id!r} should still exist"
        assert row.status == "returned", (
            f"Expected status='returned' for order_id={order_id!r}, "
            f"got status={row.status!r}"
        )

        # Assert return_reason matches
        assert row.return_reason == return_reason, (
            f"Expected return_reason={return_reason!r}, got {row.return_reason!r}"
        )

        # Assert total row count is unchanged
        row_count_after = db.query(FitProfileRow).count()
        assert row_count_after == row_count_before, (
            f"Row count changed: before={row_count_before}, after={row_count_after}"
        )
    finally:
        db.close()
