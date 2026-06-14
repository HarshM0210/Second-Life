"""
green_coin/db/repositories.py

Data-access helpers over the append-only ``coin_events`` ledger.

All reads derive state from the event log (balance = SUM(amount), CO2e total =
SUM over earned events, etc.). All writes are single INSERTs — the ledger is
never updated in place.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from green_coin.db.models import CoinEvent


class CoinLedgerRepository:
    """Repository for the Green Coin event ledger."""

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------
    @staticmethod
    def add_event(
        db: Session,
        *,
        user_id: str,
        event_type: str,
        amount: int,
        source: str,
        co2e_kg: float = 0.0,
        streak_day: int = 0,
        badge: str | None = None,
        item_id: str | None = None,
    ) -> CoinEvent:
        """Insert and flush a single ledger event, returning the persisted row."""
        event = CoinEvent(
            id=str(uuid.uuid4()),
            user_id=user_id,
            event_type=event_type,
            amount=amount,
            source=source,
            co2e_kg=co2e_kg,
            streak_day=streak_day,
            badge=badge,
            item_id=item_id,
            created_at=datetime.now(timezone.utc),
        )
        db.add(event)
        db.flush()  # assign defaults / surface integrity errors before commit
        return event

    # ------------------------------------------------------------------
    # Per-user reads
    # ------------------------------------------------------------------
    @staticmethod
    def get_balance(db: Session, user_id: str) -> int:
        """Current coin balance = SUM(amount) across all of the user's events."""
        total = (
            db.query(func.coalesce(func.sum(CoinEvent.amount), 0))
            .filter(CoinEvent.user_id == user_id)
            .scalar()
        )
        return int(total or 0)

    @staticmethod
    def get_co2e_total(db: Session, user_id: str) -> float:
        """Cumulative kg CO2e avoided across the user's *earned* events."""
        total = (
            db.query(func.coalesce(func.sum(CoinEvent.co2e_kg), 0.0))
            .filter(CoinEvent.user_id == user_id, CoinEvent.event_type == "earned")
            .scalar()
        )
        return float(total or 0.0)

    @staticmethod
    def get_history(db: Session, user_id: str, limit: int = 20) -> list[CoinEvent]:
        """Most-recent ledger events for the user, newest first."""
        return (
            db.query(CoinEvent)
            .filter(CoinEvent.user_id == user_id)
            .order_by(CoinEvent.created_at.desc(), CoinEvent.id.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_last_earn_event(db: Session, user_id: str) -> CoinEvent | None:
        """The user's most recent ``earned`` event (drives streak calculation)."""
        return (
            db.query(CoinEvent)
            .filter(CoinEvent.user_id == user_id, CoinEvent.event_type == "earned")
            .order_by(CoinEvent.created_at.desc(), CoinEvent.id.desc())
            .first()
        )

    @staticmethod
    def coins_earned_last_24h(db: Session, user_id: str) -> int:
        """Total positive coins earned by the user in the trailing 24 hours."""
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        total = (
            db.query(func.coalesce(func.sum(CoinEvent.amount), 0))
            .filter(
                CoinEvent.user_id == user_id,
                CoinEvent.event_type == "earned",
                CoinEvent.created_at >= since,
            )
            .scalar()
        )
        return int(total or 0)

    # ------------------------------------------------------------------
    # Platform-wide reads (impact ticker)
    # ------------------------------------------------------------------
    @staticmethod
    def platform_co2e_total(db: Session) -> float:
        total = (
            db.query(func.coalesce(func.sum(CoinEvent.co2e_kg), 0.0))
            .filter(CoinEvent.event_type == "earned")
            .scalar()
        )
        return float(total or 0.0)

    @staticmethod
    def platform_items_count(db: Session) -> int:
        return int(
            db.query(func.count(func.distinct(CoinEvent.item_id)))
            .filter(CoinEvent.event_type == "earned", CoinEvent.item_id.isnot(None))
            .scalar()
            or 0
        )
