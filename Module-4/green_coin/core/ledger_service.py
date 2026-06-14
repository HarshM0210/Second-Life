"""
green_coin/core/ledger_service.py

Orchestration layer that ties the CO2e engine, gamification rules, and the
ledger repository into the two core operations: *earn* and *redeem*.

Keeping this logic out of the HTTP routes means it can be unit-tested directly
against an in-memory SQLite session, and reused by both the public earn
endpoint (Module 1) and the Module 3 purchase-avoidance integration.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from green_coin.config import settings
from green_coin.core import gamification
from green_coin.core.co2e_engine import coins_earned, co2e_avoided, equivalents
from green_coin.core.gamification import Badge
from green_coin.core.rewards import get_reward
from green_coin.db.models import CoinEvent
from green_coin.db.repositories import CoinLedgerRepository

logger = logging.getLogger(__name__)


@dataclass
class EarnResult:
    coins_earned: int
    co2e_kg: float
    new_balance: int
    streak: int
    badge_unlocked: Badge | None
    equivalents: dict[str, float]
    flagged_for_review: bool


@dataclass
class RedeemResult:
    success: bool
    new_balance: int
    reward_id: str | None
    reason: str | None


class LedgerService:
    """Stateless service operating on a supplied DB session."""

    def __init__(self, repo: type[CoinLedgerRepository] = CoinLedgerRepository) -> None:
        self._repo = repo

    # ------------------------------------------------------------------
    # Earn — disposition-driven (Module 1)
    # ------------------------------------------------------------------
    def earn_for_disposition(
        self,
        db: Session,
        *,
        user_id: str,
        disposition: str,
        category: str,
        item_id: str,
        item_weight_kg: float,
        buyer_distance_km: float,
    ) -> EarnResult:
        """Compute CO2e, apply streak + cap, persist, and award any badge."""
        co2e = co2e_avoided(disposition, category, item_weight_kg, buyer_distance_km)
        base_coins = coins_earned(co2e, settings.COIN_MULTIPLIER)

        # Streak: derived from the user's last earn event.
        from datetime import datetime, timezone

        last = self._repo.get_last_earn_event(db, user_id)
        now = datetime.now(timezone.utc)
        streak = gamification.compute_new_streak(
            last.created_at if last else None,
            last.streak_day if last else 0,
            now,
            reset_hours=settings.STREAK_RESET_HOURS,
        )
        coins = gamification.apply_streak_multiplier(base_coins, streak)

        # Anti-abuse: cap coins per single disposition event.
        coins = min(coins, settings.EARN_CAP_PER_EVENT)

        # Badge: compare cumulative CO2e before and after this event.
        prev_total = self._repo.get_co2e_total(db, user_id)
        badge = gamification.newly_earned_badge(prev_total, prev_total + co2e)

        self._repo.add_event(
            db,
            user_id=user_id,
            event_type="earned",
            amount=coins,
            source=f"disposition:{disposition}",
            co2e_kg=co2e,
            streak_day=streak,
            badge=badge.slug if badge else None,
            item_id=item_id,
        )

        # Record the badge unlock as its own ledger event (audit trail).
        if badge is not None:
            self._repo.add_event(
                db,
                user_id=user_id,
                event_type="badge_earned",
                amount=0,
                source=f"badge:{badge.slug}",
                co2e_kg=0.0,
                streak_day=streak,
                badge=badge.slug,
                item_id=item_id,
            )

        flagged = self._repo.coins_earned_last_24h(db, user_id) > settings.FRAUD_DAILY_THRESHOLD
        if flagged:
            logger.warning(
                "green_coin_fraud_flag user_id=%s reason='>%d coins in 24h'",
                user_id, settings.FRAUD_DAILY_THRESHOLD,
            )

        db.commit()

        return EarnResult(
            coins_earned=coins,
            co2e_kg=round(co2e, 2),
            new_balance=self._repo.get_balance(db, user_id),
            streak=streak,
            badge_unlocked=badge,
            equivalents=equivalents(co2e),
            flagged_for_review=flagged,
        )

    # ------------------------------------------------------------------
    # Earn — fixed-coin behavioural bonus (Module 2 / 3 / 5)
    # ------------------------------------------------------------------
    def earn_bonus(
        self,
        db: Session,
        *,
        user_id: str,
        coins: int,
        source: str,
        item_id: str | None = None,
    ) -> int:
        """Grant a fixed bonus (capped) and return the new balance."""
        coins = min(max(coins, 0), settings.EARN_CAP_PER_EVENT)
        self._repo.add_event(
            db,
            user_id=user_id,
            event_type="earned",
            amount=coins,
            source=f"bonus:{source}",
            co2e_kg=0.0,
            streak_day=0,
            item_id=item_id,
        )
        db.commit()
        return self._repo.get_balance(db, user_id)

    # ------------------------------------------------------------------
    # Redeem
    # ------------------------------------------------------------------
    def redeem(self, db: Session, *, user_id: str, reward_id: str) -> RedeemResult:
        """Spend coins on a catalog reward if the balance covers its cost."""
        reward = get_reward(reward_id)
        if reward is None:
            return RedeemResult(False, self._repo.get_balance(db, user_id), None, "unknown_reward")

        balance = self._repo.get_balance(db, user_id)
        if balance < reward.cost:
            return RedeemResult(False, balance, reward_id, "insufficient_balance")

        self._repo.add_event(
            db,
            user_id=user_id,
            event_type="redeemed",
            amount=-reward.cost,
            source=f"reward:{reward_id}",
            co2e_kg=0.0,
        )
        db.commit()
        return RedeemResult(True, self._repo.get_balance(db, user_id), reward_id, None)


def history_to_dicts(events: list[CoinEvent]) -> list[dict]:
    """Serialise ledger rows for the wallet response."""
    return [
        {
            "id": e.id,
            "event_type": e.event_type,
            "amount": e.amount,
            "source": e.source,
            "co2e_kg": round(e.co2e_kg, 2),
            "streak_day": e.streak_day,
            "badge": e.badge,
            "item_id": e.item_id,
            "created_at": e.created_at.isoformat() if e.created_at else "",
        }
        for e in events
    ]
