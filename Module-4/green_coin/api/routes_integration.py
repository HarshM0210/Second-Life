"""
green_coin/api/routes_integration.py

Inter-module integration endpoints.

POST /api/v4/purchase-avoidance
    Consumed by Module 3 (Return Prevention). When a customer heeds an
    intervention and keeps an item instead of returning it, Module 3 emits a
    ``purchase_avoidance`` event here. We reward the kept item with a fixed
    bonus (KEPT_AFTER_NUDGE_COINS) — closing the prevention → reward loop.

The payload mirrors Module 3's ``PurchaseAvoidanceEvent`` schema exactly. We
accept it leniently (extra/missing optional fields tolerated) so a schema bump
in Module 3 never breaks the contract.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from green_coin.config import settings
from green_coin.core.ledger_service import LedgerService
from green_coin.db.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v4", tags=["integration"])


class PurchaseAvoidanceEvent(BaseModel):
    """Inbound event from Module 3 (mirrors its emitter schema)."""

    event_type: str = "purchase_avoidance"
    customer_id: str
    product_id: str
    risk_score: float
    intervention_type: Optional[str] = None
    session_id: str
    emitted_at: datetime


class PurchaseAvoidanceAck(BaseModel):
    accepted: bool
    coins_earned: int
    new_balance: int


def _get_service() -> LedgerService:
    return LedgerService()


@router.post("/purchase-avoidance", response_model=PurchaseAvoidanceAck)
def purchase_avoidance(
    event: PurchaseAvoidanceEvent,
    db: Session = Depends(get_db),
    service: LedgerService = Depends(_get_service),
) -> Any:
    """Reward a customer for keeping an item after a Module 3 nudge."""
    try:
        new_balance = service.earn_bonus(
            db,
            user_id=event.customer_id,
            coins=settings.KEPT_AFTER_NUDGE_COINS,
            source="kept_after_nudge",
            item_id=event.product_id,
        )
        logger.info(
            "purchase_avoidance_rewarded customer_id=%s product_id=%s coins=%d",
            event.customer_id, event.product_id, settings.KEPT_AFTER_NUDGE_COINS,
        )
        return PurchaseAvoidanceAck(
            accepted=True,
            coins_earned=settings.KEPT_AFTER_NUDGE_COINS,
            new_balance=new_balance,
        )
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.error(
            "purchase_avoidance_error customer_id=%s error=%s", event.customer_id, exc
        )
        return JSONResponse(status_code=503, content={"detail": "Service temporarily unavailable"})
