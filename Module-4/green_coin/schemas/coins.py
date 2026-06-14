"""
green_coin/schemas/coins.py

Pydantic I/O models for the Green Coin endpoints. These define the inter-module
contract: Module 1 (disposition) calls ``/earn``; Module 2/3/5 fire bonus
earns; the React wallet consumes ``/wallet`` and ``/impact/summary``.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from green_coin.core.co2e_engine import Disposition


# ---------------------------------------------------------------------------
# Shared sub-models
# ---------------------------------------------------------------------------


class Equivalents(BaseModel):
    """Human-relatable CO2e equivalents shown in the UI."""

    trees_per_month: float
    km_not_driven: float
    phone_charges: float


class BadgeOut(BaseModel):
    """A badge as returned to clients."""

    slug: str
    name: str
    icon: str
    threshold_kg: float
    equivalent: str
    unlocked: bool = True


# ---------------------------------------------------------------------------
# Earn (Module 1 disposition flow)
# ---------------------------------------------------------------------------


class EarnRequest(BaseModel):
    """Body for POST /api/v4/coins/earn — issued after a return disposition."""

    user_id: str
    disposition: Disposition
    category: str
    item_id: str
    item_weight_kg: float = Field(default=0.5, gt=0)
    buyer_distance_km: float = Field(default=0.0, ge=0)


class EarnResponse(BaseModel):
    coins_earned: int
    co2e_kg: float
    new_balance: int
    streak: int
    badge_unlocked: Optional[BadgeOut] = None
    equivalents: Equivalents
    flagged_for_review: bool = False


# ---------------------------------------------------------------------------
# Bonus earn (Module 2 / 3 / 5 behavioural triggers)
# ---------------------------------------------------------------------------


class BonusEarnRequest(BaseModel):
    """Body for POST /api/v4/coins/earn/bonus — fixed-coin behavioural rewards.

    ``source`` records *why* the coins were granted (e.g. "chose_renewed",
    "slow_shipping", "kept_after_nudge", "p2p_referral", "first_activation").
    """

    user_id: str
    coins: int = Field(..., gt=0)
    source: str
    item_id: Optional[str] = None


class BonusEarnResponse(BaseModel):
    coins_earned: int
    new_balance: int
    source: str


# ---------------------------------------------------------------------------
# Redeem
# ---------------------------------------------------------------------------


class RedeemRequest(BaseModel):
    """Body for POST /api/v4/coins/redeem."""

    user_id: str
    reward_id: str


class RedeemResponse(BaseModel):
    success: bool
    new_balance: int
    reward_id: Optional[str] = None
    reason: Optional[str] = None


# ---------------------------------------------------------------------------
# Wallet & impact
# ---------------------------------------------------------------------------


class HistoryItem(BaseModel):
    id: str
    event_type: str
    amount: int
    source: str
    co2e_kg: float
    streak_day: int
    badge: Optional[str] = None
    item_id: Optional[str] = None
    created_at: str


class WalletResponse(BaseModel):
    user_id: str
    balance: int
    co2e_total_kg: float
    equivalents: Equivalents
    badges: list[BadgeOut]
    history: list[HistoryItem]


class ImpactSummaryResponse(BaseModel):
    co2e_avoided_kg: float
    items_given_second_life: int
    trees_equivalent: float


# ---------------------------------------------------------------------------
# Rewards catalog
# ---------------------------------------------------------------------------


class Reward(BaseModel):
    reward_id: str
    name: str
    cost: int
    description: str
    category: str  # e.g. "renewed_discount" | "membership" | "certificate" | "donation"
