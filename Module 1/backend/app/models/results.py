"""
Result dataclasses for pipeline components.

Each dataclass represents the output of a specific pipeline stage.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Literal


@dataclass
class ReturnWindowResult:
    """Output of the Return Window Validator."""

    eligible: bool
    window_days: int
    days_elapsed: int
    expiry_date: date
    message: str | None = None


@dataclass
class AnomalyResult:
    """Output of the Anomaly Detector (PatchCore inference)."""

    anomaly_severity: float  # 0.0–1.0, max across images
    heatmap_uri: str
    model_available: bool
    failure_reason: str | None = None


@dataclass
class WearResult:
    """Output of the Wear Detector (OpenCV-based analysis)."""

    wear_detection_penalty: float  # 0.0–1.0
    wear_indicators: list[str] = field(default_factory=list)
    analysis_performed: bool = True


@dataclass
class IntentResult:
    """Output of the Intent Classifier."""

    return_reason_penalty: float  # 0.05–0.35
    penalty_category: Literal["high", "medium", "low"]
    inconsistency_flags: list[str] = field(default_factory=list)
    unclassified: bool = False


@dataclass
class HealthScoreResult:
    """Output of the Health Score Computer."""

    health_score: int  # 0–100 (clamped)
    breakdown: "ScoreBreakdownResult"
    condition: Literal["Excellent", "Good", "Fair", "Poor"]


@dataclass
class ScoreBreakdownResult:
    """Weighted contribution breakdown for health score computation."""

    w1_anomaly_contribution: float
    w2_defect_contribution: float
    w3_reason_contribution: float
    w4_wear_contribution: float


@dataclass
class FraudScanResult:
    """Output of the Fraud Scanner (Social Connect)."""

    social_scan_performed: bool
    accounts_scanned: list[str] = field(default_factory=list)
    product_found_in_social: bool = False
    fraud_confidence: float = 0.0  # 0.0–1.0
    evidence_posts: list[dict] = field(default_factory=list)
    scan_window: dict[str, str] = field(default_factory=dict)


@dataclass
class DispositionResult:
    """Output of the Disposition Router."""

    disposition: str  # resell | refurbish | donate | recycle | return_to_seller | manual_review
    gate_applied: str  # "A", "B", "category_override", "safety_hold"
    flags: list[str] = field(default_factory=list)
