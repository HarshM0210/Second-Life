"""
return_prevention/schemas/risk.py

Pydantic I/O models for the risk-score endpoint.

Requirements: 1.7
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class InterventionType(str, Enum):
    """Intervention strategy types, in priority order."""

    SIZE_GUIDANCE = "SIZE_GUIDANCE"
    SOCIAL_PROOF = "SOCIAL_PROOF"
    COMPARISON_NUDGE = "COMPARISON_NUDGE"
    CLARIFYING_QA = "CLARIFYING_QA"


class RiskScoreRequest(BaseModel):
    """Request body for POST /api/v1/risk-score."""

    customer_id: str
    product_id: str
    page_dwell_seconds: float = Field(..., ge=0)
    is_buy_now: bool
    seller_id: Optional[str] = None
    product_price: Optional[float] = None
    is_sale_active: bool = False


class RiskScoreResponse(BaseModel):
    """Response body for POST /api/v1/risk-score."""

    risk_score: float
    intervention_type: Optional[InterventionType] = None
    intervention_copy: Optional[str] = None
    taxonomy_miss: bool = False
