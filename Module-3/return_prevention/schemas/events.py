"""
return_prevention/schemas/events.py

Pydantic schema for the purchase_avoidance event emitted to Green_Coin_Service.

Requirements: 8.1
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class PurchaseAvoidanceEvent(BaseModel):
    """Event emitted when a customer heeds an intervention and avoids a purchase."""

    event_type: str = "purchase_avoidance"
    customer_id: str
    product_id: str
    risk_score: float
    intervention_type: str | None = None
    session_id: str
    emitted_at: datetime
