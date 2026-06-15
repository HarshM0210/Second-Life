"""
Data models for the Grading, Fraud Detection & Quality System.

Exports all Pydantic models and result dataclasses.
"""

from app.models.health_card import FraudSignal, HealthCard, ScoreBreakdown
from app.models.qa import Question, SupplementaryInput, ValidationResult
from app.models.results import (
    AnomalyResult,
    DispositionResult,
    FraudScanResult,
    HealthScoreResult,
    IntentResult,
    ReturnWindowResult,
    ScoreBreakdownResult,
    WearResult,
)
from app.models.return_request import CatalogMetadata, ReturnRequest

__all__ = [
    # Health Card models
    "HealthCard",
    "FraudSignal",
    "ScoreBreakdown",
    # Return request models
    "ReturnRequest",
    "CatalogMetadata",
    # Result dataclasses
    "ReturnWindowResult",
    "AnomalyResult",
    "WearResult",
    "IntentResult",
    "HealthScoreResult",
    "ScoreBreakdownResult",
    "FraudScanResult",
    "DispositionResult",
    # QA models
    "Question",
    "SupplementaryInput",
    "ValidationResult",
]
