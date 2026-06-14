"""
Property Test 9 — Price Band Feature Correctness

For any customer with a known high-return price band, in_user_high_return_price_band
SHALL be true when the product price falls within that band and false for product
prices that fall in any other band.

**Validates: Requirements 2.6**
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from return_prevention.core.feature_assembler import _price_in_band
from return_prevention.db.database import Base
from return_prevention.db.repositories import PriceBandProfileRepository


# ---------------------------------------------------------------------------
# Price band boundaries (from design doc):
#   '0-500'      → [0, 500)
#   '501-2000'   → [500, 2000)
#   '2001-10000' → [2000, 10000)
#   '10000+'     → [10000, +∞)
# ---------------------------------------------------------------------------

VALID_BANDS = ["0-500", "501-2000", "2001-10000", "10000+"]

BAND_RANGES: dict[str, tuple[float, float]] = {
    "0-500": (0.0, 500.0),
    "501-2000": (500.0, 2000.0),
    "2001-10000": (2000.0, 10000.0),
    "10000+": (10000.0, 50000.0),  # capped for test generation
}


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

def customer_price_band_strategy():
    """
    Generate (customer_id, high_return_band, product_price) tuples.

    - customer_id: non-empty text
    - high_return_band: one of the 4 valid bands
    - product_price: float in [0.0, 50000.0]
    """
    return st.tuples(
        st.text(min_size=1, max_size=50),  # customer_id
        st.sampled_from(VALID_BANDS),  # high_return_band
        st.floats(min_value=0.0, max_value=50000.0, allow_nan=False, allow_infinity=False),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db_session():
    """Create a fresh in-memory SQLite session with schema."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return Session()


def _seed_price_band_profile(db, customer_id: str, high_return_band: str):
    """
    Seed the PriceBandProfileRepository so that the given band has the
    highest return rate for the customer.
    """
    # Give the high-return band a return rate of 0.8, and all others 0.1
    for band in VALID_BANDS:
        return_rate = 0.8 if band == high_return_band else 0.1
        PriceBandProfileRepository.upsert(
            db=db,
            customer_id=customer_id,
            price_band=band,
            total_orders=10,
            total_returns=int(10 * return_rate),
            return_rate=return_rate,
        )


# ---------------------------------------------------------------------------
# Property Test
# ---------------------------------------------------------------------------

@given(data=customer_price_band_strategy())
@settings(max_examples=50, deadline=5000)
def test_price_band_feature_correctness(data):
    """
    Property 9: Price Band Feature Correctness.

    For any customer with a known high-return price band:
    - in_user_high_return_price_band == True when price falls within that band
    - in_user_high_return_price_band == False when price falls outside that band

    Price band boundaries:
      [0, 500), [500, 2000), [2000, 10000), [10000, +∞)

    **Validates: Requirements 2.6**
    """
    customer_id, high_return_band, product_price = data

    db = _make_db_session()
    try:
        # Seed the price band profile
        _seed_price_band_profile(db, customer_id, high_return_band)

        # Verify get_high_return_band returns the expected band
        retrieved_band = PriceBandProfileRepository.get_high_return_band(
            db, customer_id
        )
        assert retrieved_band == high_return_band, (
            f"Expected high return band={high_return_band!r}, "
            f"got {retrieved_band!r}"
        )

        # Check if the product price falls in the high-return band
        result = _price_in_band(product_price, high_return_band)

        # Compute expected result based on band boundaries
        lower, upper = BAND_RANGES[high_return_band]
        # The actual boundary from feature_assembler uses [lower, upper) semantics
        # except for '10000+' which is [10000, +inf)
        if high_return_band == "10000+":
            expected = product_price >= lower
        else:
            expected = lower <= product_price < upper

        assert result == expected, (
            f"_price_in_band({product_price}, {high_return_band!r}) returned "
            f"{result}, expected {expected}. "
            f"Band range: [{lower}, {upper})"
        )
    finally:
        db.close()
