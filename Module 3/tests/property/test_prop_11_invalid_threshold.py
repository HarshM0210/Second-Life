"""
Property Test 11 — Invalid Threshold Is Rejected and Prior Value Retained

For any invalid RISK_THRESHOLD value (outside [0.0, 1.0] or not a valid float),
the Settings validator SHALL reject the value and retain the default (0.6).

**Validates: Requirements 5.5**
"""

from __future__ import annotations

import math

from hypothesis import given, settings as h_settings
from hypothesis import strategies as st

from return_prevention.config import Settings, _DEFAULT_RISK_THRESHOLD


def _is_valid_float_in_range(s: str) -> bool:
    """Check if a string represents a valid float in [0.0, 1.0]."""
    try:
        v = float(s)
        return 0.0 <= v <= 1.0 and not math.isnan(v) and not math.isinf(v)
    except (TypeError, ValueError):
        return False


# Strategy: generate floats outside [0.0, 1.0] (including NaN, Inf)
_invalid_floats = st.one_of(
    st.floats(max_value=-0.001, allow_nan=False, allow_infinity=False),
    st.floats(min_value=1.001, allow_nan=False, allow_infinity=False),
    st.just(float("nan")),
    st.just(float("inf")),
    st.just(float("-inf")),
)

# Strategy: generate non-numeric strings
_invalid_strings = st.text(min_size=1).filter(lambda s: not _is_valid_float_in_range(s))

# Combined strategy of invalid threshold values
_invalid_threshold_strategy = st.one_of(_invalid_floats, _invalid_strings)


@given(invalid_value=_invalid_threshold_strategy)
@h_settings(max_examples=50, deadline=10000)
def test_invalid_threshold_retains_default(invalid_value):
    """
    Property 11: Invalid Threshold Is Rejected and Prior Value Retained.

    For any value that is not a valid float in [0.0, 1.0], the Settings
    validator should fall back to the default threshold value (0.6).

    **Validates: Requirements 5.5**
    """
    # Call the validator directly — it's a classmethod on Settings
    result = Settings.validate_risk_threshold(invalid_value)

    # The validator should always return the default for invalid inputs
    assert result == _DEFAULT_RISK_THRESHOLD, (
        f"Expected validator to return default {_DEFAULT_RISK_THRESHOLD} "
        f"for invalid input {invalid_value!r}, but got {result}"
    )


@given(valid_value=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False))
@h_settings(max_examples=50, deadline=10000)
def test_valid_threshold_is_accepted(valid_value):
    """
    Complement check: valid threshold values in [0.0, 1.0] should be accepted
    and returned as-is by the validator.

    **Validates: Requirements 5.5**
    """
    result = Settings.validate_risk_threshold(valid_value)

    assert result == valid_value, (
        f"Expected validator to accept valid input {valid_value}, "
        f"but got {result}"
    )
