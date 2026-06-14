"""
green_coin/api/routes_coins.py

Public Green Coin API under /api/v4/coins:

  POST /earn               — issue coins for a return disposition (Module 1)
  POST /earn/bonus         — fixed-coin behavioural reward (Module 2/5/onboarding)
  POST /redeem             — spend coins on a Renewed-only reward
  GET  /wallet/{user_id}   — balance, CO2e total, badges, history (wallet UI)
  GET  /impact/summary     — platform-wide ticker
  GET  /rewards            — redeemable catalog
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from green_coin.config import settings
from green_coin.core import gamification
from green_coin.core.co2e_engine import equivalents
from green_coin.core.gamification import Badge
from green_coin.core.ledger_service import LedgerService, history_to_dicts
from green_coin.core.rewards import get_rewards
from green_coin.db.database import get_db
from green_coin.db.repositories import CoinLedgerRepository
from green_coin.schemas.coins import (
    BadgeOut,
    BonusEarnRequest,
    BonusEarnResponse,
    EarnRequest,
    EarnResponse,
    Equivalents,
    ImpactSummaryResponse,
    RedeemRequest,
    RedeemResponse,
    Reward,
    WalletResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v4/coins", tags=["coins"])


def _get_service() -> LedgerService:
    return LedgerService()


def _badge_out(badge: Badge | None, unlocked: bool = True) -> BadgeOut | None:
    if badge is None:
        return None
    return BadgeOut(
        slug=badge.slug,
        name=badge.name,
        icon=badge.icon,
        threshold_kg=badge.threshold_kg,
        equivalent=badge.equivalent,
        unlocked=unlocked,
    )


@router.post("/earn", response_model=EarnResponse)
def earn(
    req: EarnRequest,
    db: Session = Depends(get_db),
    service: LedgerService = Depends(_get_service),
) -> Any:
    """Issue Green Coins for a return disposition (called by Module 1)."""
    try:
        result = service.earn_for_disposition(
            db,
            user_id=req.user_id,
            disposition=req.disposition.value,
            category=req.category,
            item_id=req.item_id,
            item_weight_kg=req.item_weight_kg,
            buyer_distance_km=req.buyer_distance_km,
        )
        return EarnResponse(
            coins_earned=result.coins_earned,
            co2e_kg=result.co2e_kg,
            new_balance=result.new_balance,
            streak=result.streak,
            badge_unlocked=_badge_out(result.badge_unlocked),
            equivalents=Equivalents(**result.equivalents),
            flagged_for_review=result.flagged_for_review,
        )
    except Exception as exc:  # noqa: BLE001 - surface as 503 like Module 3
        db.rollback()
        logger.error("earn_endpoint_error user_id=%s error=%s", req.user_id, exc)
        return JSONResponse(status_code=503, content={"detail": "Service temporarily unavailable"})


@router.post("/earn/bonus", response_model=BonusEarnResponse)
def earn_bonus(
    req: BonusEarnRequest,
    db: Session = Depends(get_db),
    service: LedgerService = Depends(_get_service),
) -> Any:
    """Grant a fixed-coin behavioural bonus (chose Renewed, slow shipping, etc.)."""
    try:
        new_balance = service.earn_bonus(
            db, user_id=req.user_id, coins=req.coins, source=req.source, item_id=req.item_id
        )
        # Report the amount actually credited (the service caps at EARN_CAP_PER_EVENT).
        credited = min(req.coins, settings.EARN_CAP_PER_EVENT)
        return BonusEarnResponse(
            coins_earned=credited,
            new_balance=new_balance,
            source=req.source,
        )
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.error("earn_bonus_endpoint_error user_id=%s error=%s", req.user_id, exc)
        return JSONResponse(status_code=503, content={"detail": "Service temporarily unavailable"})


@router.post("/redeem", response_model=RedeemResponse)
def redeem(
    req: RedeemRequest,
    db: Session = Depends(get_db),
    service: LedgerService = Depends(_get_service),
) -> Any:
    """Redeem coins against a Renewed-only reward."""
    try:
        result = service.redeem(db, user_id=req.user_id, reward_id=req.reward_id)
        return RedeemResponse(
            success=result.success,
            new_balance=result.new_balance,
            reward_id=result.reward_id,
            reason=result.reason,
        )
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.error("redeem_endpoint_error user_id=%s error=%s", req.user_id, exc)
        return JSONResponse(status_code=503, content={"detail": "Service temporarily unavailable"})


@router.get("/wallet/{user_id}", response_model=WalletResponse)
def wallet(user_id: str, db: Session = Depends(get_db)) -> Any:
    """Full wallet view for the React UI: balance, CO2e, badges, history."""
    try:
        balance = CoinLedgerRepository.get_balance(db, user_id)
        co2e = CoinLedgerRepository.get_co2e_total(db, user_id)
        history = CoinLedgerRepository.get_history(db, user_id, limit=20)

        unlocked_slugs = {b.slug for b in gamification.unlocked_badges(co2e)}
        badges = [
            _badge_out(b, unlocked=b.slug in unlocked_slugs)
            for b in gamification.BADGES
        ]

        return WalletResponse(
            user_id=user_id,
            balance=balance,
            co2e_total_kg=round(co2e, 2),
            equivalents=Equivalents(**equivalents(co2e)),
            badges=[b for b in badges if b is not None],
            history=history_to_dicts(history),
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("wallet_endpoint_error user_id=%s error=%s", user_id, exc)
        return JSONResponse(status_code=503, content={"detail": "Service temporarily unavailable"})


@router.get("/impact/summary", response_model=ImpactSummaryResponse)
def impact_summary(db: Session = Depends(get_db)) -> Any:
    """Platform-wide impact totals — powers the live demo ticker."""
    try:
        total_co2e = CoinLedgerRepository.platform_co2e_total(db)
        items = CoinLedgerRepository.platform_items_count(db)
        return ImpactSummaryResponse(
            co2e_avoided_kg=round(total_co2e, 1),
            items_given_second_life=items,
            trees_equivalent=round(total_co2e / 0.83, 1),
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("impact_summary_endpoint_error error=%s", exc)
        return JSONResponse(status_code=503, content={"detail": "Service temporarily unavailable"})


@router.get("/rewards", response_model=list[Reward])
def rewards() -> Any:
    """Return the redeemable rewards catalog."""
    try:
        return list(get_rewards().values())
    except Exception as exc:  # noqa: BLE001
        logger.error("rewards_endpoint_error error=%s", exc)
        return JSONResponse(status_code=503, content={"detail": "Service temporarily unavailable"})
