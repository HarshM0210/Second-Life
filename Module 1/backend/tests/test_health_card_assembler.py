"""
Unit tests for the Health Card Assembler service.

Tests cover:
- Source field determination (p2p_fraud_divert vs standard_return)
- Fraud signal block completeness
- Confidence calculation based on pipeline component availability
- All required Health Card schema fields are present
- Null/default handling when pipeline components are unavailable

Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 18.1, 18.4
"""

import pytest

from app.models.health_card import FraudSignal, HealthCard
from app.models.results import (
    AnomalyResult,
    DispositionResult,
    FraudScanResult,
    HealthScoreResult,
    ScoreBreakdownResult,
)
from app.services.health_card_assembler import HealthCardAssembler


@pytest.fixture
def assembler():
    return HealthCardAssembler()


@pytest.fixture
def score_result():
    return HealthScoreResult(
        health_score=85,
        breakdown=ScoreBreakdownResult(
            w1_anomaly_contribution=5.0,
            w2_defect_contribution=3.0,
            w3_reason_contribution=4.0,
            w4_wear_contribution=3.0,
        ),
        condition="Good",
    )


@pytest.fixture
def anomaly_result():
    return AnomalyResult(
        anomaly_severity=0.2,
        heatmap_uri="s3://bucket/item123_heatmap.png",
        model_available=True,
        failure_reason=None,
    )


@pytest.fixture
def disposition_result():
    return DispositionResult(
        disposition="refurbish",
        gate_applied="B",
        flags=[],
    )


@pytest.fixture
def fraud_scan_result():
    return FraudScanResult(
        social_scan_performed=True,
        accounts_scanned=["instagram", "facebook"],
        product_found_in_social=True,
        fraud_confidence=0.75,
        evidence_posts=[],
        scan_window={"from": "2026-01-01", "to": "2026-02-01"},
    )


class TestSourceFieldDetermination:
    """Test source field logic: p2p_fraud_divert vs standard_return."""

    def test_p2p_fraud_divert_all_conditions_met(
        self, assembler, score_result, anomaly_result, disposition_result, fraud_scan_result
    ):
        """source = p2p_fraud_divert when fraud >= 0.60 AND Clothing & Footwear AND chose P2P."""
        card = assembler.assemble(
            score_result=score_result,
            anomaly_result=anomaly_result,
            fraud_confidence=0.75,
            disposition_result=disposition_result,
            justification="Good. Detected: none. No structural anomalies. Functional check: pass. Warranty: 5 months remaining.",
            fraud_scan_result=fraud_scan_result,
            p2p_offered=True,
            customer_chose_p2p=True,
            warranty_months=5,
            defects=[],
            category="Clothing & Footwear",
        )
        assert card.source == "p2p_fraud_divert"

    def test_standard_return_fraud_below_threshold(
        self, assembler, score_result, anomaly_result, disposition_result
    ):
        """source = standard_return when fraud_confidence < 0.60."""
        card = assembler.assemble(
            score_result=score_result,
            anomaly_result=anomaly_result,
            fraud_confidence=0.50,
            disposition_result=disposition_result,
            justification="Good. Detected: none. No structural anomalies. Functional check: pass. Warranty: 5 months remaining.",
            fraud_scan_result=None,
            p2p_offered=False,
            customer_chose_p2p=False,
            warranty_months=5,
            defects=[],
            category="Clothing & Footwear",
        )
        assert card.source == "standard_return"

    def test_standard_return_wrong_category(
        self, assembler, score_result, anomaly_result, disposition_result
    ):
        """source = standard_return when category is NOT Clothing & Footwear."""
        card = assembler.assemble(
            score_result=score_result,
            anomaly_result=anomaly_result,
            fraud_confidence=0.80,
            disposition_result=disposition_result,
            justification="Good. Detected: none. No structural anomalies. Functional check: pass. Warranty: 5 months remaining.",
            fraud_scan_result=None,
            p2p_offered=False,
            customer_chose_p2p=True,
            warranty_months=5,
            defects=[],
            category="Electronics",
        )
        assert card.source == "standard_return"

    def test_standard_return_customer_declined_p2p(
        self, assembler, score_result, anomaly_result, disposition_result, fraud_scan_result
    ):
        """source = standard_return when customer did NOT choose P2P."""
        card = assembler.assemble(
            score_result=score_result,
            anomaly_result=anomaly_result,
            fraud_confidence=0.75,
            disposition_result=disposition_result,
            justification="Good. Detected: none. No structural anomalies. Functional check: pass. Warranty: 5 months remaining.",
            fraud_scan_result=fraud_scan_result,
            p2p_offered=True,
            customer_chose_p2p=False,
            warranty_months=5,
            defects=[],
            category="Clothing & Footwear",
        )
        assert card.source == "standard_return"

    def test_p2p_fraud_divert_at_exact_threshold(
        self, assembler, score_result, anomaly_result, disposition_result, fraud_scan_result
    ):
        """source = p2p_fraud_divert at exactly 0.60 threshold."""
        card = assembler.assemble(
            score_result=score_result,
            anomaly_result=anomaly_result,
            fraud_confidence=0.60,
            disposition_result=disposition_result,
            justification="Good. Detected: none. No structural anomalies. Functional check: pass. Warranty: 5 months remaining.",
            fraud_scan_result=fraud_scan_result,
            p2p_offered=True,
            customer_chose_p2p=True,
            warranty_months=5,
            defects=[],
            category="Clothing & Footwear",
        )
        assert card.source == "p2p_fraud_divert"

    def test_standard_return_just_below_threshold(
        self, assembler, score_result, anomaly_result, disposition_result, fraud_scan_result
    ):
        """source = standard_return at 0.59 (just below threshold)."""
        card = assembler.assemble(
            score_result=score_result,
            anomaly_result=anomaly_result,
            fraud_confidence=0.59,
            disposition_result=disposition_result,
            justification="Good. Detected: none. No structural anomalies. Functional check: pass. Warranty: 5 months remaining.",
            fraud_scan_result=fraud_scan_result,
            p2p_offered=True,
            customer_chose_p2p=True,
            warranty_months=5,
            defects=[],
            category="Clothing & Footwear",
        )
        assert card.source == "standard_return"


class TestFraudSignalBlock:
    """Test fraud_signal block completeness and correctness."""

    def test_fraud_signal_with_scan_performed(
        self, assembler, score_result, anomaly_result, disposition_result, fraud_scan_result
    ):
        """fraud_signal reflects scan results when fraud scan was performed."""
        card = assembler.assemble(
            score_result=score_result,
            anomaly_result=anomaly_result,
            fraud_confidence=0.75,
            disposition_result=disposition_result,
            justification="Good. Detected: none. No structural anomalies. Functional check: pass. Warranty: 5 months remaining.",
            fraud_scan_result=fraud_scan_result,
            p2p_offered=True,
            customer_chose_p2p=True,
            warranty_months=5,
            defects=[],
            category="Clothing & Footwear",
        )
        assert card.fraud_signal.social_scan_performed is True
        assert card.fraud_signal.product_found_in_social is True
        assert card.fraud_signal.fraud_confidence == 0.75
        assert card.fraud_signal.p2p_offered is True
        assert card.fraud_signal.customer_chose_p2p is True

    def test_fraud_signal_without_scan(
        self, assembler, score_result, anomaly_result, disposition_result
    ):
        """fraud_signal defaults social fields when scan not performed."""
        card = assembler.assemble(
            score_result=score_result,
            anomaly_result=anomaly_result,
            fraud_confidence=0.20,
            disposition_result=disposition_result,
            justification="Good. Detected: none. No structural anomalies. Functional check: pass. Warranty: 5 months remaining.",
            fraud_scan_result=None,
            p2p_offered=False,
            customer_chose_p2p=False,
            warranty_months=5,
            defects=[],
            category="Electronics",
        )
        assert card.fraud_signal.social_scan_performed is False
        assert card.fraud_signal.product_found_in_social is False
        assert card.fraud_signal.fraud_confidence == 0.20
        assert card.fraud_signal.p2p_offered is False
        assert card.fraud_signal.customer_chose_p2p is False

    def test_fraud_signal_is_complete_instance(
        self, assembler, score_result, anomaly_result, disposition_result
    ):
        """fraud_signal block is a complete FraudSignal instance with all fields."""
        card = assembler.assemble(
            score_result=score_result,
            anomaly_result=anomaly_result,
            fraud_confidence=0.30,
            disposition_result=disposition_result,
            justification="test justification",
            fraud_scan_result=None,
            p2p_offered=False,
            customer_chose_p2p=False,
            warranty_months=3,
            defects=["minor scratch"],
            category="Electronics",
        )
        assert isinstance(card.fraud_signal, FraudSignal)
        # Verify all required FraudSignal fields exist
        assert hasattr(card.fraud_signal, "social_scan_performed")
        assert hasattr(card.fraud_signal, "product_found_in_social")
        assert hasattr(card.fraud_signal, "fraud_confidence")
        assert hasattr(card.fraud_signal, "p2p_offered")
        assert hasattr(card.fraud_signal, "customer_chose_p2p")


class TestConfidenceCalculation:
    """Test confidence calculation based on pipeline component availability."""

    def test_full_confidence_all_components_succeed(
        self, assembler, score_result, disposition_result
    ):
        """confidence = 1.0 when all pipeline components succeed."""
        anomaly = AnomalyResult(
            anomaly_severity=0.2,
            heatmap_uri="s3://bucket/heatmap.png",
            model_available=True,
            failure_reason=None,
        )
        card = assembler.assemble(
            score_result=score_result,
            anomaly_result=anomaly,
            fraud_confidence=0.10,
            disposition_result=disposition_result,
            justification="test justification",
            fraud_scan_result=None,
            p2p_offered=False,
            customer_chose_p2p=False,
            warranty_months=5,
            defects=[],
            category="Electronics",
        )
        assert card.confidence == 1.0

    def test_reduced_confidence_anomaly_model_unavailable(
        self, assembler, score_result, disposition_result
    ):
        """confidence = 0.7 when anomaly model is unavailable."""
        anomaly = AnomalyResult(
            anomaly_severity=0.0,
            heatmap_uri="",
            model_available=False,
            failure_reason="anomaly_model_unavailable",
        )
        card = assembler.assemble(
            score_result=score_result,
            anomaly_result=anomaly,
            fraud_confidence=0.10,
            disposition_result=disposition_result,
            justification="test justification",
            fraud_scan_result=None,
            p2p_offered=False,
            customer_chose_p2p=False,
            warranty_months=5,
            defects=["anomaly_model_unavailable"],
            category="Electronics",
        )
        assert card.confidence == 0.7


class TestHealthCardSchemaCompleteness:
    """Test that all required Health Card fields are present."""

    def test_all_required_fields_present(
        self, assembler, score_result, anomaly_result, disposition_result
    ):
        """HealthCard contains all required schema fields."""
        card = assembler.assemble(
            score_result=score_result,
            anomaly_result=anomaly_result,
            fraud_confidence=0.10,
            disposition_result=disposition_result,
            justification="Good. Detected: none. No structural anomalies. Functional check: pass. Warranty: 5 months remaining.",
            fraud_scan_result=None,
            p2p_offered=False,
            customer_chose_p2p=False,
            warranty_months=5,
            defects=["minor scratch"],
            category="Electronics",
        )
        assert isinstance(card, HealthCard)
        assert card.condition == "Good"
        assert card.health_score == 85
        assert 0.0 <= card.confidence <= 1.0
        assert card.warranty_left_months == 5
        assert card.defects == ["minor scratch"]
        assert card.anomaly_heatmap_uri == "s3://bucket/item123_heatmap.png"
        assert card.justification != ""
        assert card.disposition == "refurbish"
        assert card.source in ("standard_return", "p2p_fraud_divert")
        assert isinstance(card.fraud_signal, FraudSignal)

    def test_health_card_serializes_to_json(
        self, assembler, score_result, anomaly_result, disposition_result
    ):
        """HealthCard can be serialized to JSON with all fields."""
        card = assembler.assemble(
            score_result=score_result,
            anomaly_result=anomaly_result,
            fraud_confidence=0.10,
            disposition_result=disposition_result,
            justification="Good. Detected: none. No structural anomalies. Functional check: pass. Warranty: 5 months remaining.",
            fraud_scan_result=None,
            p2p_offered=False,
            customer_chose_p2p=False,
            warranty_months=5,
            defects=[],
            category="Electronics",
        )
        json_data = card.model_dump()
        required_keys = {
            "condition", "health_score", "confidence", "warranty_left_months",
            "defects", "anomaly_heatmap_uri", "justification", "disposition",
            "source", "fraud_signal",
        }
        assert required_keys.issubset(json_data.keys())

    def test_fraud_signal_json_has_all_fields(
        self, assembler, score_result, anomaly_result, disposition_result
    ):
        """fraud_signal block in JSON contains all required sub-fields."""
        card = assembler.assemble(
            score_result=score_result,
            anomaly_result=anomaly_result,
            fraud_confidence=0.30,
            disposition_result=disposition_result,
            justification="test",
            fraud_scan_result=None,
            p2p_offered=False,
            customer_chose_p2p=False,
            warranty_months=3,
            defects=[],
            category="Electronics",
        )
        fraud_json = card.fraud_signal.model_dump()
        required_fraud_keys = {
            "social_scan_performed", "product_found_in_social",
            "fraud_confidence", "p2p_offered", "customer_chose_p2p",
        }
        assert required_fraud_keys.issubset(fraud_json.keys())


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_defects_list(
        self, assembler, score_result, anomaly_result, disposition_result
    ):
        """Empty defects list is handled correctly."""
        card = assembler.assemble(
            score_result=score_result,
            anomaly_result=anomaly_result,
            fraud_confidence=0.10,
            disposition_result=disposition_result,
            justification="test",
            fraud_scan_result=None,
            p2p_offered=False,
            customer_chose_p2p=False,
            warranty_months=0,
            defects=[],
            category="Electronics",
        )
        assert card.defects == []

    def test_zero_warranty_months(
        self, assembler, score_result, anomaly_result, disposition_result
    ):
        """Zero warranty months is valid."""
        card = assembler.assemble(
            score_result=score_result,
            anomaly_result=anomaly_result,
            fraud_confidence=0.10,
            disposition_result=disposition_result,
            justification="test",
            fraud_scan_result=None,
            p2p_offered=False,
            customer_chose_p2p=False,
            warranty_months=0,
            defects=[],
            category="Electronics",
        )
        assert card.warranty_left_months == 0

    def test_max_fraud_confidence(
        self, assembler, score_result, anomaly_result, disposition_result, fraud_scan_result
    ):
        """fraud_confidence=1.0 with all P2P conditions → p2p_fraud_divert."""
        card = assembler.assemble(
            score_result=score_result,
            anomaly_result=anomaly_result,
            fraud_confidence=1.0,
            disposition_result=disposition_result,
            justification="test",
            fraud_scan_result=fraud_scan_result,
            p2p_offered=True,
            customer_chose_p2p=True,
            warranty_months=5,
            defects=[],
            category="Clothing & Footwear",
        )
        assert card.source == "p2p_fraud_divert"
        assert card.fraud_signal.fraud_confidence == 1.0

    def test_zero_fraud_confidence(
        self, assembler, score_result, anomaly_result, disposition_result
    ):
        """fraud_confidence=0.0 always results in standard_return."""
        card = assembler.assemble(
            score_result=score_result,
            anomaly_result=anomaly_result,
            fraud_confidence=0.0,
            disposition_result=disposition_result,
            justification="test",
            fraud_scan_result=None,
            p2p_offered=False,
            customer_chose_p2p=False,
            warranty_months=5,
            defects=[],
            category="Clothing & Footwear",
        )
        assert card.source == "standard_return"
        assert card.fraud_signal.fraud_confidence == 0.0

    def test_health_score_boundaries(self, assembler, anomaly_result, disposition_result):
        """HealthCard handles boundary health scores (0 and 100)."""
        # Score 0
        score_zero = HealthScoreResult(
            health_score=0,
            breakdown=ScoreBreakdownResult(25.0, 25.0, 25.0, 25.0),
            condition="Poor",
        )
        card = assembler.assemble(
            score_result=score_zero,
            anomaly_result=anomaly_result,
            fraud_confidence=0.10,
            disposition_result=disposition_result,
            justification="test",
            fraud_scan_result=None,
            p2p_offered=False,
            customer_chose_p2p=False,
            warranty_months=0,
            defects=[],
            category="Electronics",
        )
        assert card.health_score == 0
        assert card.condition == "Poor"

        # Score 100
        score_hundred = HealthScoreResult(
            health_score=100,
            breakdown=ScoreBreakdownResult(0.0, 0.0, 0.0, 0.0),
            condition="Excellent",
        )
        card = assembler.assemble(
            score_result=score_hundred,
            anomaly_result=anomaly_result,
            fraud_confidence=0.10,
            disposition_result=disposition_result,
            justification="test",
            fraud_scan_result=None,
            p2p_offered=False,
            customer_chose_p2p=False,
            warranty_months=12,
            defects=[],
            category="Electronics",
        )
        assert card.health_score == 100
        assert card.condition == "Excellent"

    def test_all_disposition_types(self, assembler, score_result, anomaly_result):
        """All disposition types can be assembled into a HealthCard."""
        dispositions = ["resell", "refurbish", "donate", "recycle", "return_to_seller", "manual_review"]
        for disp in dispositions:
            result = DispositionResult(disposition=disp, gate_applied="B", flags=[])
            card = assembler.assemble(
                score_result=score_result,
                anomaly_result=anomaly_result,
                fraud_confidence=0.10,
                disposition_result=result,
                justification="test",
                fraud_scan_result=None,
                p2p_offered=False,
                customer_chose_p2p=False,
                warranty_months=5,
                defects=[],
                category="Electronics",
            )
            assert card.disposition == disp
