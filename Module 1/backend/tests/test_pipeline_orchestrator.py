"""
Unit tests for PipelineOrchestrator service.

Tests parallel execution, error handling, cross-validation, fraud aggregation,
disposition routing, and Health Card assembly coordination.

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 16.1, 16.2, 16.3, 16.4, 16.5, 16.6
"""

import asyncio
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from app.models.health_card import FraudSignal, HealthCard
from app.models.results import (
    AnomalyResult,
    DispositionResult,
    FraudScanResult,
    HealthScoreResult,
    IntentResult,
    ScoreBreakdownResult,
    WearResult,
)
from app.services.pipeline_orchestrator import (
    COMPONENT_HARD_TIMEOUT_S,
    FRAUD_SCAN_CATEGORY,
    PipelineError,
    PipelineInput,
    PipelineOrchestrator,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_images() -> list[np.ndarray]:
    """Create sample test images."""
    return [np.zeros((100, 100, 3), dtype=np.uint8)]


@pytest.fixture
def sample_input(sample_images: list[np.ndarray]) -> PipelineInput:
    """Standard pipeline input for Clothing & Footwear category."""
    return PipelineInput(
        images=sample_images,
        video_frames=[],
        qa_answers={"return_reason": "Changed my mind / no longer needed"},
        category="Clothing & Footwear",
        product_value=150.0,
        customer_id="CUST-001",
        connected_accounts=["instagram_user1"],
        purchase_date="2025-01-01",
        return_date="2025-01-10",
        warranty_remaining_months=6,
    )


@pytest.fixture
def electronics_input(sample_images: list[np.ndarray]) -> PipelineInput:
    """Pipeline input for Electronics category (no fraud scan)."""
    return PipelineInput(
        images=sample_images,
        video_frames=[],
        qa_answers={"return_reason": "Item is defective / not working"},
        category="Electronics",
        product_value=500.0,
        customer_id="CUST-002",
        connected_accounts=[],
        purchase_date="2025-01-01",
        return_date="2025-01-20",
        warranty_remaining_months=11,
    )


@pytest.fixture
def mock_anomaly_result() -> AnomalyResult:
    return AnomalyResult(
        anomaly_severity=0.3,
        heatmap_uri="s3://heatmaps/test_heatmap.png",
        model_available=True,
        failure_reason=None,
    )


@pytest.fixture
def mock_wear_result() -> WearResult:
    return WearResult(
        wear_detection_penalty=0.2,
        wear_indicators=["sole_wear"],
        analysis_performed=True,
    )


@pytest.fixture
def mock_intent_result() -> IntentResult:
    return IntentResult(
        return_reason_penalty=0.05,
        penalty_category="low",
        inconsistency_flags=[],
        unclassified=False,
    )


@pytest.fixture
def mock_score_result() -> HealthScoreResult:
    return HealthScoreResult(
        health_score=82,
        breakdown=ScoreBreakdownResult(
            w1_anomaly_contribution=6.0,
            w2_defect_contribution=6.0,
            w3_reason_contribution=1.0,
            w4_wear_contribution=5.0,
        ),
        condition="Good",
    )


@pytest.fixture
def mock_fraud_scan_result() -> FraudScanResult:
    return FraudScanResult(
        social_scan_performed=True,
        accounts_scanned=["instagram_user1"],
        product_found_in_social=False,
        fraud_confidence=0.15,
        evidence_posts=[],
        scan_window={"from": "2025-01-01", "to": "2025-01-10"},
    )


@pytest.fixture
def mock_disposition_result() -> DispositionResult:
    return DispositionResult(
        disposition="refurbish",
        gate_applied="B",
        flags=[],
    )


@pytest.fixture
def mock_health_card() -> HealthCard:
    return HealthCard(
        condition="Good",
        health_score=82,
        confidence=1.0,
        warranty_left_months=6,
        defects=["sole_wear"],
        anomaly_heatmap_uri="s3://heatmaps/test_heatmap.png",
        justification="Good. Detected: sole_wear. No structural anomalies. Functional check: pass. Warranty: 6 months remaining.",
        disposition="refurbish",
        source="standard_return",
        fraud_signal=FraudSignal(
            social_scan_performed=True,
            product_found_in_social=False,
            fraud_confidence=0.15,
            p2p_offered=False,
            customer_chose_p2p=False,
        ),
    )


def _build_orchestrator(
    anomaly_result=None,
    wear_result=None,
    intent_result=None,
    fraud_scan_result=None,
    score_result=None,
    disposition_result=None,
    health_card=None,
):
    """Build a PipelineOrchestrator with mocked dependencies."""
    anomaly_detector = MagicMock()
    if anomaly_result is not None:
        anomaly_detector.detect = MagicMock(return_value=anomaly_result)

    wear_detector = MagicMock()
    if wear_result is not None:
        wear_detector.detect = MagicMock(return_value=wear_result)

    intent_classifier = MagicMock()
    if intent_result is not None:
        intent_classifier.classify = MagicMock(return_value=intent_result)
    intent_classifier.check_inconsistencies = MagicMock(return_value=[])

    fraud_scanner = MagicMock()
    if fraud_scan_result is not None:
        fraud_scanner.scan = MagicMock(return_value=fraud_scan_result)

    health_score_computer = MagicMock()
    if score_result is not None:
        health_score_computer.compute = AsyncMock(return_value=score_result)

    justification_engine = MagicMock()
    justification_engine.generate = MagicMock(
        return_value="Good. Detected: sole_wear. No structural anomalies. Functional check: pass. Warranty: 6 months remaining."
    )

    disposition_router = MagicMock()
    if disposition_result is not None:
        disposition_router.route = AsyncMock(return_value=disposition_result)

    health_card_assembler = MagicMock()
    if health_card is not None:
        health_card_assembler.assemble = MagicMock(return_value=health_card)

    orchestrator = PipelineOrchestrator(
        anomaly_detector=anomaly_detector,
        wear_detector=wear_detector,
        intent_classifier=intent_classifier,
        fraud_scanner=fraud_scanner,
        health_score_computer=health_score_computer,
        justification_engine=justification_engine,
        disposition_router=disposition_router,
        health_card_assembler=health_card_assembler,
    )

    return orchestrator


# ---------------------------------------------------------------------------
# Test: Successful end-to-end pipeline execution
# ---------------------------------------------------------------------------


class TestSuccessfulExecution:
    async def test_clothing_category_runs_fraud_scanner(
        self,
        sample_input,
        mock_anomaly_result,
        mock_wear_result,
        mock_intent_result,
        mock_fraud_scan_result,
        mock_score_result,
        mock_disposition_result,
        mock_health_card,
    ):
        """Clothing & Footwear category triggers fraud scan in parallel (Req 5.1)."""
        orchestrator = _build_orchestrator(
            anomaly_result=mock_anomaly_result,
            wear_result=mock_wear_result,
            intent_result=mock_intent_result,
            fraud_scan_result=mock_fraud_scan_result,
            score_result=mock_score_result,
            disposition_result=mock_disposition_result,
            health_card=mock_health_card,
        )

        result = await orchestrator.execute(sample_input)

        assert isinstance(result, HealthCard)
        # Verify fraud scanner was called
        orchestrator._fraud_scanner.scan.assert_called_once()

    async def test_electronics_category_skips_fraud_scanner(
        self,
        electronics_input,
        mock_anomaly_result,
        mock_wear_result,
        mock_intent_result,
        mock_score_result,
        mock_disposition_result,
        mock_health_card,
    ):
        """Non-Clothing category skips fraud scan entirely (Req 5.2, 16.4)."""
        orchestrator = _build_orchestrator(
            anomaly_result=mock_anomaly_result,
            wear_result=mock_wear_result,
            intent_result=mock_intent_result,
            fraud_scan_result=None,
            score_result=mock_score_result,
            disposition_result=mock_disposition_result,
            health_card=mock_health_card,
        )

        result = await orchestrator.execute(electronics_input)

        assert isinstance(result, HealthCard)
        # Fraud scanner should NOT have been called
        orchestrator._fraud_scanner.scan.assert_not_called()

    async def test_returns_health_card_on_success(
        self,
        sample_input,
        mock_anomaly_result,
        mock_wear_result,
        mock_intent_result,
        mock_fraud_scan_result,
        mock_score_result,
        mock_disposition_result,
        mock_health_card,
    ):
        """Pipeline returns a complete HealthCard on success (Req 5.3)."""
        orchestrator = _build_orchestrator(
            anomaly_result=mock_anomaly_result,
            wear_result=mock_wear_result,
            intent_result=mock_intent_result,
            fraud_scan_result=mock_fraud_scan_result,
            score_result=mock_score_result,
            disposition_result=mock_disposition_result,
            health_card=mock_health_card,
        )

        result = await orchestrator.execute(sample_input)

        assert isinstance(result, HealthCard)
        assert result.health_score == 82
        assert result.condition == "Good"
        assert result.disposition == "refurbish"

    async def test_health_score_computer_called_with_cross_validated_penalty(
        self,
        sample_input,
        mock_anomaly_result,
        mock_wear_result,
        mock_intent_result,
        mock_fraud_scan_result,
        mock_score_result,
        mock_disposition_result,
        mock_health_card,
    ):
        """Cross-validation uses the pessimistic (max) penalty (Req 21.1)."""
        orchestrator = _build_orchestrator(
            anomaly_result=mock_anomaly_result,
            wear_result=mock_wear_result,
            intent_result=mock_intent_result,
            fraud_scan_result=mock_fraud_scan_result,
            score_result=mock_score_result,
            disposition_result=mock_disposition_result,
            health_card=mock_health_card,
        )

        await orchestrator.execute(sample_input)

        # Verify health score computer was called
        orchestrator._health_score_computer.compute.assert_called_once()
        call_kwargs = orchestrator._health_score_computer.compute.call_args[1]

        # max(intent penalty=0.05, wear penalty=0.2) = 0.2
        assert call_kwargs["wear_detection_penalty"] == 0.2


# ---------------------------------------------------------------------------
# Test: Parallel execution behavior
# ---------------------------------------------------------------------------


class TestParallelExecution:
    async def test_grader_components_run_concurrently(
        self,
        sample_input,
        mock_anomaly_result,
        mock_wear_result,
        mock_intent_result,
        mock_fraud_scan_result,
        mock_score_result,
        mock_disposition_result,
        mock_health_card,
    ):
        """All grader sub-components (anomaly, wear, intent) are called (Req 5.1)."""
        orchestrator = _build_orchestrator(
            anomaly_result=mock_anomaly_result,
            wear_result=mock_wear_result,
            intent_result=mock_intent_result,
            fraud_scan_result=mock_fraud_scan_result,
            score_result=mock_score_result,
            disposition_result=mock_disposition_result,
            health_card=mock_health_card,
        )

        await orchestrator.execute(sample_input)

        orchestrator._anomaly_detector.detect.assert_called_once()
        orchestrator._wear_detector.detect.assert_called_once()
        orchestrator._intent_classifier.classify.assert_called_once()

    async def test_anomaly_detector_receives_images_plus_frames(
        self, mock_anomaly_result, mock_wear_result, mock_intent_result,
        mock_fraud_scan_result, mock_score_result, mock_disposition_result,
        mock_health_card,
    ):
        """Anomaly detector receives both images and video frames combined."""
        images = [np.zeros((50, 50, 3), dtype=np.uint8)]
        frames = [np.ones((50, 50, 3), dtype=np.uint8)]
        input_data = PipelineInput(
            images=images,
            video_frames=frames,
            qa_answers={"return_reason": "Changed my mind"},
            category="Clothing & Footwear",
            product_value=100.0,
            customer_id="CUST-001",
            connected_accounts=["ig_user"],
            purchase_date="2025-01-01",
            return_date="2025-01-10",
            warranty_remaining_months=3,
        )

        orchestrator = _build_orchestrator(
            anomaly_result=mock_anomaly_result,
            wear_result=mock_wear_result,
            intent_result=mock_intent_result,
            fraud_scan_result=mock_fraud_scan_result,
            score_result=mock_score_result,
            disposition_result=mock_disposition_result,
            health_card=mock_health_card,
        )

        await orchestrator.execute(input_data)

        # Anomaly detector should receive images + video_frames
        call_args = orchestrator._anomaly_detector.detect.call_args[0]
        assert len(call_args[0]) == 2  # 1 image + 1 frame


# ---------------------------------------------------------------------------
# Test: Component failure handling (Req 5.5)
# ---------------------------------------------------------------------------


class TestComponentFailureHandling:
    async def test_anomaly_detector_timeout_returns_worst_case(
        self, sample_input, mock_wear_result, mock_intent_result,
        mock_fraud_scan_result, mock_score_result, mock_disposition_result,
        mock_health_card,
    ):
        """Anomaly detector timeout → severity=1.0 (worst case)."""
        # Create an anomaly detector that times out
        anomaly_detector = MagicMock()
        anomaly_detector.detect = MagicMock(side_effect=Exception("Timeout simulation"))

        orchestrator = PipelineOrchestrator(
            anomaly_detector=anomaly_detector,
            wear_detector=MagicMock(detect=MagicMock(return_value=mock_wear_result)),
            intent_classifier=MagicMock(
                classify=MagicMock(return_value=mock_intent_result),
                check_inconsistencies=MagicMock(return_value=[]),
            ),
            fraud_scanner=MagicMock(scan=MagicMock(return_value=mock_fraud_scan_result)),
            health_score_computer=MagicMock(compute=AsyncMock(return_value=mock_score_result)),
            justification_engine=MagicMock(
                generate=MagicMock(return_value="Test justification.")
            ),
            disposition_router=MagicMock(route=AsyncMock(return_value=mock_disposition_result)),
            health_card_assembler=MagicMock(assemble=MagicMock(return_value=mock_health_card)),
        )

        result = await orchestrator.execute(sample_input)

        # Pipeline should still produce a result (degraded, but not failed)
        assert isinstance(result, HealthCard)

    async def test_wear_detector_failure_returns_zero_penalty(
        self, sample_input, mock_anomaly_result, mock_intent_result,
        mock_fraud_scan_result, mock_score_result, mock_disposition_result,
        mock_health_card,
    ):
        """Wear detector failure → penalty=0.0, analysis_performed=False."""
        wear_detector = MagicMock()
        wear_detector.detect = MagicMock(side_effect=Exception("Processing failure"))

        orchestrator = PipelineOrchestrator(
            anomaly_detector=MagicMock(
                detect=MagicMock(return_value=mock_anomaly_result)
            ),
            wear_detector=wear_detector,
            intent_classifier=MagicMock(
                classify=MagicMock(return_value=mock_intent_result),
                check_inconsistencies=MagicMock(return_value=[]),
            ),
            fraud_scanner=MagicMock(scan=MagicMock(return_value=mock_fraud_scan_result)),
            health_score_computer=MagicMock(compute=AsyncMock(return_value=mock_score_result)),
            justification_engine=MagicMock(
                generate=MagicMock(return_value="Test justification.")
            ),
            disposition_router=MagicMock(route=AsyncMock(return_value=mock_disposition_result)),
            health_card_assembler=MagicMock(assemble=MagicMock(return_value=mock_health_card)),
        )

        result = await orchestrator.execute(sample_input)

        # Should still succeed with degraded wear data
        assert isinstance(result, HealthCard)

    async def test_intent_classifier_failure_assigns_medium_penalty(
        self, sample_input, mock_anomaly_result, mock_wear_result,
        mock_fraud_scan_result, mock_score_result, mock_disposition_result,
        mock_health_card,
    ):
        """Intent classifier failure → default medium penalty (0.15)."""
        intent_classifier = MagicMock()
        intent_classifier.classify = MagicMock(side_effect=Exception("Classification error"))
        intent_classifier.check_inconsistencies = MagicMock(return_value=[])

        orchestrator = PipelineOrchestrator(
            anomaly_detector=MagicMock(
                detect=MagicMock(return_value=mock_anomaly_result)
            ),
            wear_detector=MagicMock(detect=MagicMock(return_value=mock_wear_result)),
            intent_classifier=intent_classifier,
            fraud_scanner=MagicMock(scan=MagicMock(return_value=mock_fraud_scan_result)),
            health_score_computer=MagicMock(compute=AsyncMock(return_value=mock_score_result)),
            justification_engine=MagicMock(
                generate=MagicMock(return_value="Test justification.")
            ),
            disposition_router=MagicMock(route=AsyncMock(return_value=mock_disposition_result)),
            health_card_assembler=MagicMock(assemble=MagicMock(return_value=mock_health_card)),
        )

        result = await orchestrator.execute(sample_input)

        assert isinstance(result, HealthCard)

    async def test_fraud_scanner_failure_proceeds_without_social_data(
        self, sample_input, mock_anomaly_result, mock_wear_result,
        mock_intent_result, mock_score_result, mock_disposition_result,
        mock_health_card,
    ):
        """Fraud scanner failure → social_scan_performed=False (Req 16.1, 16.2)."""
        fraud_scanner = MagicMock()
        fraud_scanner.scan = MagicMock(side_effect=Exception("Social API unavailable"))

        orchestrator = PipelineOrchestrator(
            anomaly_detector=MagicMock(
                detect=MagicMock(return_value=mock_anomaly_result)
            ),
            wear_detector=MagicMock(detect=MagicMock(return_value=mock_wear_result)),
            intent_classifier=MagicMock(
                classify=MagicMock(return_value=mock_intent_result),
                check_inconsistencies=MagicMock(return_value=[]),
            ),
            fraud_scanner=fraud_scanner,
            health_score_computer=MagicMock(compute=AsyncMock(return_value=mock_score_result)),
            justification_engine=MagicMock(
                generate=MagicMock(return_value="Test justification.")
            ),
            disposition_router=MagicMock(route=AsyncMock(return_value=mock_disposition_result)),
            health_card_assembler=MagicMock(assemble=MagicMock(return_value=mock_health_card)),
        )

        result = await orchestrator.execute(sample_input)

        # Pipeline should still succeed
        assert isinstance(result, HealthCard)

    async def test_complete_grader_failure_returns_pipeline_error(
        self, sample_input, mock_fraud_scan_result,
    ):
        """If all grader components fail → PipelineError (Req 5.6)."""
        # All components fail
        anomaly_detector = MagicMock()
        anomaly_detector.detect = MagicMock(side_effect=Exception("Failed"))

        wear_detector = MagicMock()
        wear_detector.detect = MagicMock(side_effect=Exception("Failed"))

        intent_classifier = MagicMock()
        intent_classifier.classify = MagicMock(side_effect=Exception("Failed"))
        intent_classifier.check_inconsistencies = MagicMock(return_value=[])

        orchestrator = PipelineOrchestrator(
            anomaly_detector=anomaly_detector,
            wear_detector=wear_detector,
            intent_classifier=intent_classifier,
            fraud_scanner=MagicMock(scan=MagicMock(return_value=mock_fraud_scan_result)),
        )

        result = await orchestrator.execute(sample_input)

        assert isinstance(result, PipelineError)
        assert result.failed_component == "grader"


# ---------------------------------------------------------------------------
# Test: Graceful degradation (Req 16.1-16.6)
# ---------------------------------------------------------------------------


class TestGracefulDegradation:
    async def test_no_connected_accounts_clothing_still_works(
        self,
        mock_anomaly_result,
        mock_wear_result,
        mock_intent_result,
        mock_score_result,
        mock_disposition_result,
        mock_health_card,
    ):
        """Clothing & Footwear with no connected accounts → no social penalty (Req 16.1, 16.2)."""
        input_data = PipelineInput(
            images=[np.zeros((50, 50, 3), dtype=np.uint8)],
            video_frames=[],
            qa_answers={"return_reason": "Changed my mind"},
            category="Clothing & Footwear",
            product_value=100.0,
            customer_id="CUST-NO-SOCIAL",
            connected_accounts=[],  # No connected accounts
            purchase_date="2025-01-01",
            return_date="2025-01-10",
            warranty_remaining_months=3,
        )

        # FraudScanner.scan returns not performed when no accounts
        fraud_scan_result = FraudScanResult(
            social_scan_performed=False,
            accounts_scanned=[],
            product_found_in_social=False,
            fraud_confidence=0.0,
            evidence_posts=[],
            scan_window={"from": "2025-01-01", "to": "2025-01-10"},
        )

        orchestrator = _build_orchestrator(
            anomaly_result=mock_anomaly_result,
            wear_result=mock_wear_result,
            intent_result=mock_intent_result,
            fraud_scan_result=fraud_scan_result,
            score_result=mock_score_result,
            disposition_result=mock_disposition_result,
            health_card=mock_health_card,
        )

        result = await orchestrator.execute(input_data)

        assert isinstance(result, HealthCard)

    async def test_non_clothing_category_produces_complete_health_card(
        self,
        electronics_input,
        mock_anomaly_result,
        mock_wear_result,
        mock_intent_result,
        mock_score_result,
        mock_disposition_result,
        mock_health_card,
    ):
        """Non-Clothing category produces a full Health Card without fraud scan (Req 16.4, 16.6)."""
        orchestrator = _build_orchestrator(
            anomaly_result=mock_anomaly_result,
            wear_result=mock_wear_result,
            intent_result=mock_intent_result,
            fraud_scan_result=None,
            score_result=mock_score_result,
            disposition_result=mock_disposition_result,
            health_card=mock_health_card,
        )

        result = await orchestrator.execute(electronics_input)

        assert isinstance(result, HealthCard)
        # Health card assembler should have been called with fraud_scan_result=None
        call_kwargs = orchestrator._health_card_assembler.assemble.call_args[1]
        assert call_kwargs["fraud_scan_result"] is None


# ---------------------------------------------------------------------------
# Test: Cross-validation and fraud escalation
# ---------------------------------------------------------------------------


class TestCrossValidation:
    async def test_pessimistic_penalty_used_when_wear_higher(
        self,
        sample_input,
        mock_anomaly_result,
        mock_fraud_scan_result,
        mock_score_result,
        mock_disposition_result,
        mock_health_card,
    ):
        """When wear penalty > intent penalty, wear penalty is used."""
        # Wear penalty = 0.5 > intent penalty = 0.05
        high_wear = WearResult(
            wear_detection_penalty=0.5,
            wear_indicators=["fabric_stress"],
            analysis_performed=True,
        )
        low_intent = IntentResult(
            return_reason_penalty=0.05,
            penalty_category="low",
            inconsistency_flags=[],
            unclassified=False,
        )

        orchestrator = _build_orchestrator(
            anomaly_result=mock_anomaly_result,
            wear_result=high_wear,
            intent_result=low_intent,
            fraud_scan_result=mock_fraud_scan_result,
            score_result=mock_score_result,
            disposition_result=mock_disposition_result,
            health_card=mock_health_card,
        )

        await orchestrator.execute(sample_input)

        call_kwargs = orchestrator._health_score_computer.compute.call_args[1]
        # max(0.05, 0.5) = 0.5
        assert call_kwargs["wear_detection_penalty"] == 0.5

    async def test_pessimistic_penalty_used_when_intent_higher(
        self,
        sample_input,
        mock_anomaly_result,
        mock_fraud_scan_result,
        mock_score_result,
        mock_disposition_result,
        mock_health_card,
    ):
        """When intent penalty > wear penalty, intent penalty is used."""
        low_wear = WearResult(
            wear_detection_penalty=0.1,
            wear_indicators=[],
            analysis_performed=True,
        )
        high_intent = IntentResult(
            return_reason_penalty=0.35,
            penalty_category="high",
            inconsistency_flags=[],
            unclassified=False,
        )

        orchestrator = _build_orchestrator(
            anomaly_result=mock_anomaly_result,
            wear_result=low_wear,
            intent_result=high_intent,
            fraud_scan_result=mock_fraud_scan_result,
            score_result=mock_score_result,
            disposition_result=mock_disposition_result,
            health_card=mock_health_card,
        )

        await orchestrator.execute(sample_input)

        call_kwargs = orchestrator._health_score_computer.compute.call_args[1]
        # max(0.35, 0.1) = 0.35
        assert call_kwargs["wear_detection_penalty"] == 0.35


# ---------------------------------------------------------------------------
# Test: PipelineInput dataclass
# ---------------------------------------------------------------------------


class TestPipelineInput:
    def test_pipeline_input_creation(self, sample_images):
        """PipelineInput dataclass can be created with all fields."""
        input_data = PipelineInput(
            images=sample_images,
            video_frames=[],
            qa_answers={"return_reason": "test"},
            category="Electronics",
            product_value=200.0,
            customer_id="CUST-001",
            connected_accounts=[],
            purchase_date="2025-06-01",
            return_date="2025-06-15",
            warranty_remaining_months=10,
        )

        assert input_data.category == "Electronics"
        assert input_data.product_value == 200.0
        assert len(input_data.images) == 1

    def test_pipeline_input_with_video_frames(self, sample_images):
        """PipelineInput can include video frames."""
        frames = [np.zeros((100, 100, 3), dtype=np.uint8) for _ in range(5)]
        input_data = PipelineInput(
            images=sample_images,
            video_frames=frames,
            qa_answers={},
            category="Other",
            product_value=50.0,
            customer_id="CUST-002",
            connected_accounts=[],
            purchase_date="2025-01-01",
            return_date="2025-01-05",
            warranty_remaining_months=0,
        )

        assert len(input_data.video_frames) == 5


# ---------------------------------------------------------------------------
# Test: PipelineError dataclass
# ---------------------------------------------------------------------------


class TestPipelineError:
    def test_pipeline_error_creation(self):
        """PipelineError captures failure information."""
        error = PipelineError(
            message="Grading failed",
            failed_component="anomaly_detector",
            partial_results={"wear": "completed"},
        )

        assert error.message == "Grading failed"
        assert error.failed_component == "anomaly_detector"
        assert "wear" in error.partial_results

    def test_pipeline_error_default_partial_results(self):
        """PipelineError defaults to empty dict for partial_results."""
        error = PipelineError(
            message="Test failure",
            failed_component="grader",
        )

        assert error.partial_results == {}


# ---------------------------------------------------------------------------
# Test: Fraud aggregation integration
# ---------------------------------------------------------------------------


class TestFraudAggregation:
    async def test_fraud_aggregator_receives_social_signal_when_scanned(
        self,
        sample_input,
        mock_anomaly_result,
        mock_wear_result,
        mock_intent_result,
        mock_score_result,
        mock_disposition_result,
        mock_health_card,
    ):
        """When social scan is performed, its confidence is passed as social_signal."""
        scan_result = FraudScanResult(
            social_scan_performed=True,
            accounts_scanned=["ig_user1"],
            product_found_in_social=True,
            fraud_confidence=0.85,
            evidence_posts=[{"platform": "instagram", "match_confidence": 0.85}],
            scan_window={"from": "2025-01-01", "to": "2025-01-10"},
        )

        fraud_aggregator = MagicMock()
        fraud_aggregator.aggregate = MagicMock(return_value=0.6)

        orchestrator = PipelineOrchestrator(
            anomaly_detector=MagicMock(
                detect=MagicMock(return_value=mock_anomaly_result)
            ),
            wear_detector=MagicMock(detect=MagicMock(return_value=mock_wear_result)),
            intent_classifier=MagicMock(
                classify=MagicMock(return_value=mock_intent_result),
                check_inconsistencies=MagicMock(return_value=[]),
            ),
            fraud_scanner=MagicMock(scan=MagicMock(return_value=scan_result)),
            fraud_aggregator=fraud_aggregator,
            health_score_computer=MagicMock(compute=AsyncMock(return_value=mock_score_result)),
            justification_engine=MagicMock(
                generate=MagicMock(return_value="Test justification.")
            ),
            disposition_router=MagicMock(route=AsyncMock(return_value=mock_disposition_result)),
            health_card_assembler=MagicMock(assemble=MagicMock(return_value=mock_health_card)),
        )

        await orchestrator.execute(sample_input)

        # Verify fraud aggregator was called with social signal
        fraud_aggregator.aggregate.assert_called_once()
        call_kwargs = fraud_aggregator.aggregate.call_args[1]
        assert call_kwargs["social_signal"] == 0.85
        assert call_kwargs["social_scan_performed"] is True

    async def test_fraud_aggregator_no_social_signal_when_not_scanned(
        self,
        electronics_input,
        mock_anomaly_result,
        mock_wear_result,
        mock_intent_result,
        mock_score_result,
        mock_disposition_result,
        mock_health_card,
    ):
        """When fraud scan not performed, social_signal is None (Req 16.4)."""
        fraud_aggregator = MagicMock()
        fraud_aggregator.aggregate = MagicMock(return_value=0.1)

        orchestrator = PipelineOrchestrator(
            anomaly_detector=MagicMock(
                detect=MagicMock(return_value=mock_anomaly_result)
            ),
            wear_detector=MagicMock(detect=MagicMock(return_value=mock_wear_result)),
            intent_classifier=MagicMock(
                classify=MagicMock(return_value=mock_intent_result),
                check_inconsistencies=MagicMock(return_value=[]),
            ),
            fraud_scanner=MagicMock(),
            fraud_aggregator=fraud_aggregator,
            health_score_computer=MagicMock(compute=AsyncMock(return_value=mock_score_result)),
            justification_engine=MagicMock(
                generate=MagicMock(return_value="Test justification.")
            ),
            disposition_router=MagicMock(route=AsyncMock(return_value=mock_disposition_result)),
            health_card_assembler=MagicMock(assemble=MagicMock(return_value=mock_health_card)),
        )

        await orchestrator.execute(electronics_input)

        # Verify fraud aggregator called with None social signal
        call_kwargs = fraud_aggregator.aggregate.call_args[1]
        assert call_kwargs["social_signal"] is None
        assert call_kwargs["social_scan_performed"] is False


# ---------------------------------------------------------------------------
# Test: Disposition routing integration
# ---------------------------------------------------------------------------


class TestDispositionRouting:
    async def test_disposition_router_called_after_grading(
        self,
        sample_input,
        mock_anomaly_result,
        mock_wear_result,
        mock_intent_result,
        mock_fraud_scan_result,
        mock_score_result,
        mock_disposition_result,
        mock_health_card,
    ):
        """Disposition router is called with health_score and fraud_confidence."""
        orchestrator = _build_orchestrator(
            anomaly_result=mock_anomaly_result,
            wear_result=mock_wear_result,
            intent_result=mock_intent_result,
            fraud_scan_result=mock_fraud_scan_result,
            score_result=mock_score_result,
            disposition_result=mock_disposition_result,
            health_card=mock_health_card,
        )

        await orchestrator.execute(sample_input)

        orchestrator._disposition_router.route.assert_called_once()
        call_kwargs = orchestrator._disposition_router.route.call_args[1]
        assert call_kwargs["health_score"] == 82
        assert call_kwargs["category"] == "Clothing & Footwear"
        assert call_kwargs["product_value"] == 150.0


# ---------------------------------------------------------------------------
# Test: Behavioural score computation
# ---------------------------------------------------------------------------


class TestBehaviouralScore:
    def test_no_inconsistencies_returns_zero(self):
        """No inconsistency flags → behavioural score = 0.0."""
        orchestrator = PipelineOrchestrator()
        score = orchestrator._compute_behavioural_score([])
        assert score == 0.0

    def test_one_inconsistency_returns_04(self):
        """One inconsistency flag → behavioural score = 0.4."""
        orchestrator = PipelineOrchestrator()
        score = orchestrator._compute_behavioural_score(["never_used_but_wear_detected"])
        assert score == 0.4

    def test_multiple_flags_capped_at_one(self):
        """Multiple flags → capped at 1.0."""
        orchestrator = PipelineOrchestrator()
        score = orchestrator._compute_behavioural_score(
            ["flag1", "flag2", "flag3", "flag4"]
        )
        assert score == 1.0
