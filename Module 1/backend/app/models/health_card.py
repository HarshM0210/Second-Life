"""
Health Card, FraudSignal, and ScoreBreakdown Pydantic models.

These models define the inter-module contract (Health Card JSON) consumed by Modules 2–5.
"""

from typing import Literal

from pydantic import BaseModel, Field


class FraudSignal(BaseModel):
    """Fraud signal block within the Health Card."""

    social_scan_performed: bool
    product_found_in_social: bool
    fraud_confidence: float = Field(ge=0.0, le=1.0)
    p2p_offered: bool
    customer_chose_p2p: bool


class ScoreBreakdown(BaseModel):
    """Weighted contribution breakdown for health score computation."""

    w1_anomaly_contribution: float
    w2_defect_contribution: float
    w3_reason_contribution: float
    w4_wear_contribution: float


class HealthCard(BaseModel):
    """
    The Health Card JSON — inter-module contract produced by Module 1.

    Fields are never removed or renamed (append-only schema).
    """

    condition: Literal["Excellent", "Good", "Fair", "Poor"]
    health_score: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0.0, le=1.0)
    warranty_left_months: int = Field(ge=0)
    defects: list[str]
    anomaly_heatmap_uri: str
    justification: str
    disposition: Literal[
        "resell",
        "refurbish",
        "donate",
        "recycle",
        "return_to_seller",
        "manual_review",
    ]
    source: Literal["standard_return", "p2p_fraud_divert"]
    fraud_signal: FraudSignal
