"""
Property Test 8 — Unknown Order ID Return Event Is Discarded

For any return event referencing an order_id that does not exist in the
Fit_Profile table, processing the event SHALL leave the Fit_Profile table
entirely unchanged (no rows added, removed, or modified).

**Validates: Requirements 2.4**
"""

from __future__ import annotations

from hypothesis import given, settings, assume
from hypothesis import strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from return_prevention.db.database import Base
from return_prevention.db.models import FitProfileRow
from return_prevention.db.repositories import FitProfileRepository


# ---------------------------------------------------------------------------
# Pre-seeded order IDs (known to exist in the table)
# ---------------------------------------------------------------------------
_PRESEEDED_ORDER_IDS = {"ORDER_SEED_001", "ORDER_SEED_002", "ORDER_SEED_003"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db_session():
    """Create a fresh in-memory SQLite session with pre-seeded rows."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = Session()

    # Pre-seed some rows so the table is not empty
    for oid in _PRESEEDED_ORDER_IDS:
        FitProfileRepository.insert_pending(
            db=db,
            customer_id="seed_customer",
            brand="seed_brand",
            order_id=oid,
            purchased_size="M",
        )

    return db


def _snapshot_rows(db) -> list[dict]:
    """Take a snapshot of all rows as dicts for comparison."""
    rows = db.query(FitProfileRow).all()
    return [
        {
            "id": r.id,
            "customer_id": r.customer_id,
            "brand": r.brand,
            "order_id": r.order_id,
            "purchased_size": r.purchased_size,
            "status": r.status,
            "return_reason": r.return_reason,
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Property Test
# ---------------------------------------------------------------------------

@given(order_id=st.text(min_size=1, max_size=50))
@settings(max_examples=50, deadline=5000)
def test_unknown_order_return_event_is_discarded(order_id: str):
    """
    Property 8: Unknown Order ID Return Event Is Discarded.

    For any order_id that does not exist in the pre-seeded table,
    calling mark_returned leaves the table completely unchanged.

    **Validates: Requirements 2.4**
    """
    # Filter out order_ids that match the pre-seeded ones
    assume(order_id not in _PRESEEDED_ORDER_IDS)

    db = _make_db_session()
    try:
        # Snapshot before
        snapshot_before = _snapshot_rows(db)
        row_count_before = len(snapshot_before)

        # Process return event for unknown order_id
        FitProfileRepository.mark_returned(
            db=db,
            order_id=order_id,
            return_reason="some reason",
        )

        # Snapshot after
        snapshot_after = _snapshot_rows(db)
        row_count_after = len(snapshot_after)

        # Assert row count unchanged
        assert row_count_after == row_count_before, (
            f"Row count changed: before={row_count_before}, after={row_count_after}"
        )

        # Assert all row values are identical
        assert snapshot_after == snapshot_before, (
            f"Table was modified after mark_returned with unknown "
            f"order_id={order_id!r}. "
            f"Before: {snapshot_before}, After: {snapshot_after}"
        )
    finally:
        db.close()
