"""
Property Test 14 — Green Coin Tier Assignment is Exhaustive and Correct

For any risk_score in [0.6, 1.0], the coin tier assignment SHALL map to exactly
one tier:
  - [0.60, 0.75) → 10 coins
  - [0.75, 0.90) → 25 coins
  - [0.90, 1.00] → 50 coins

Every score in this range maps to exactly one tier with no gaps.

**Validates: Requirements 8.2**
"""

from __future__ import annotations

from hypothesis import given, settings as h_settings
from hypothesis import strategies as st


def compute_coins(risk_score: float) -> int:
    """
    Compute Green Coin credit tier based on risk_score.

    Tier boundaries (from design doc and Requirements 8.2):
      - [0.60, 0.75) → 10 coins
      - [0.75, 0.90) → 25 coins
      - [0.90, 1.00] → 50 coins
    """
    if 0.60 <= risk_score < 0.75:
        return 10
    elif 0.75 <= risk_score < 0.90:
        return 25
    elif 0.90 <= risk_score <= 1.00:
        return 50
    else:
        raise ValueError(
            f"risk_score {risk_score} is outside the eligible range [0.6, 1.0]"
        )


@given(risk_score=st.floats(min_value=0.6, max_value=1.0, allow_nan=False, allow_infinity=False))
@h_settings(max_examples=50, deadline=10000)
def test_green_coin_tier_assignment_exhaustive_and_correct(risk_score: float):
    """
    Property 14: Green Coin Tier Assignment is Exhaustive and Correct.

    For each risk_score in [0.6, 1.0]:
      - Assert coins == 10 for [0.60, 0.75)
      - Assert coins == 25 for [0.75, 0.90)
      - Assert coins == 50 for [0.90, 1.00]
      - Assert every score maps to exactly one tier

    **Validates: Requirements 8.2**
    """
    coins = compute_coins(risk_score)

    # Verify the score maps to the correct tier
    if 0.60 <= risk_score < 0.75:
        assert coins == 10, (
            f"Expected 10 coins for risk_score={risk_score} in [0.60, 0.75), "
            f"got {coins}"
        )
    elif 0.75 <= risk_score < 0.90:
        assert coins == 25, (
            f"Expected 25 coins for risk_score={risk_score} in [0.75, 0.90), "
            f"got {coins}"
        )
    elif 0.90 <= risk_score <= 1.00:
        assert coins == 50, (
            f"Expected 50 coins for risk_score={risk_score} in [0.90, 1.00], "
            f"got {coins}"
        )

    # Assert the result is one of the valid coin values (exactly one tier)
    assert coins in (10, 25, 50), (
        f"Coin value {coins} is not one of the valid tiers (10, 25, 50) "
        f"for risk_score={risk_score}"
    )
