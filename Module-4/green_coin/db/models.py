"""
green_coin/db/models.py

ORM model for the append-only Green Coin ledger.

The ledger is *event-sourced*: we never store a mutable balance. Every earn,
redeem, expiry, and badge award is an immutable row, and a user's balance is
always ``SUM(amount)``. This is the architecturally correct pattern for a
points/credits system — it gives a full audit trail, makes fraud
investigation a query rather than a guess, and makes expiry a 10-line script.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Column, DateTime, Float, Index, Integer, String, func

from green_coin.db.database import Base


class CoinEvent(Base):
    """A single immutable entry in the Green Coin ledger."""

    __tablename__ = "coin_events"

    id = Column(String, primary_key=True)  # uuid4
    user_id = Column(String, nullable=False)

    # earned | redeemed | expired | badge_earned
    event_type = Column(String, nullable=False)

    # positive == earned, negative == redeemed/expired; 0 for badge_earned.
    amount = Column(Integer, nullable=False, default=0)

    # e.g. "disposition:DONATE_LOCAL", "bonus:chose_renewed", "reward:prime_1month".
    source = Column(String, nullable=False)

    co2e_kg = Column(Float, nullable=False, default=0.0)
    streak_day = Column(Integer, nullable=False, default=0)
    badge = Column(String, nullable=True)
    item_id = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "event_type IN ('earned', 'redeemed', 'expired', 'badge_earned')",
            name="ck_coin_events_event_type",
        ),
        Index("idx_coin_events_user", "user_id"),
        Index("idx_coin_events_user_type", "user_id", "event_type"),
        Index("idx_coin_events_created_at", "created_at"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<CoinEvent(id={self.id!r}, user_id={self.user_id!r}, "
            f"event_type={self.event_type!r}, amount={self.amount}, "
            f"source={self.source!r})>"
        )
