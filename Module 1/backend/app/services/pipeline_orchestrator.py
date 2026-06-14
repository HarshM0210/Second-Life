"""
Pipeline Orchestrator service.

Coordinates the end-to-end grading and fraud detection pipeline with
parallel execution (asyncio.gather), cross-validation, fraud aggregation,
disposition routing, and Health Card assembly.

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 16.1, 16.2, 16.3, 16.4, 16.5, 16.6
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Union

import numpy as np

from app.models.health_card import HealthCard
from app.models.results import (
    AnomalyResult,
    DispositionResult,
    FraudScanResult,
    HealthScoreResult,
    IntentResult,
    WearResult,
)
from app.services.anomaly_detector import AnomalyDetector
from app.services.cross_validator import CrossValidator
from app.services.disposition_router import DispositionRouter
from app.services.fraud_aggregator import FraudAggregator
from app.services.fraud_scanner import FraudScanner
from app.services.health_card_assembler import HealthCardAssembler
from app.services.health_score import HealthScoreComputer
from app.services.intent_classifier import IntentClassifier
from app.services.justification import JustificationEngine
from app.services.wear_detector import WearDetector

logger = logging.getLogger(__name__)

# Budget and timeout configuration
TOTAL_BUDGET_MS: float = 2000.0
COMPONENT_HARD_TIMEOUT_S: float = 5.0

# Category that triggers parallel fraud scanning
FRAUD_SCAN_CATEGORY: str = "Clothing & Footwear"

# Anomaly threshold for justification phrases
DEFAULT_ANOMALY_THRESHOLD: float = 0.30


@dataclass
class PipelineInput:
    """Input data for the grading/fraud pipeline."""

    images: list[np.ndarray]
    video_frames: list[np.ndarray]
    qa_answers: dict[str, str]
    category: str
    product_value: float
    customer_id: str
    connected_accounts: list[str]
    purchase_date: str
    return_date: str
    warranty_remaining_months: int


@dataclass
class PipelineError:
    """Represents a pipeline-level failure."""

    message: str
    failed_component: str
    partial_results: dict = field(default_factory=dict)


class PipelineOrchestrator:
    """Coordinates the end-to-end grading and fraud detection pipeline.

    Orchestrates:
    1. Parallel execution: Grader (Anomaly + Wear + Intent) + Fraud Scanner
    2. Cross-validation (pessimistic signal)
    3. Fraud aggregation
    4. Disposition routing
    5. Health Card assembly

    Total budget: 2000ms. Component hard timeout: 5000ms.
    """

    def __init__(
        self,
        anomaly_detector: AnomalyDetector | None = None,
        wear_detector: WearDetector | None = None,
        intent_classifier: IntentClassifier | None = None,
        fraud_scanner: FraudScanner | None = None,
        cross_validator: CrossValidator | None = None,
        fraud_aggregator: FraudAggregator | None = None,
        health_score_computer: HealthScoreComputer | None = None,
        justification_engine: JustificationEngine | None = None,
        disposition_router: DispositionRouter | None = None,
        health_card_assembler: HealthCardAssembler | None = None,
        anomaly_threshold: float = DEFAULT_ANOMALY_THRESHOLD,
    ) -> None:
        self._anomaly_detector = anomaly_detector or AnomalyDetector()
        self._wear_detector = wear_detector or WearDetector()
        self._intent_classifier = intent_classifier or IntentClassifier()
        self._fraud_scanner = fraud_scanner or FraudScanner()
        self._cross_validator = cross_validator or CrossValidator()
        self._fraud_aggregator = fraud_aggregator or FraudAggregator()
        self._health_score_computer = health_score_computer or HealthScoreComputer()
        self._justification_engine = justification_engine or JustificationEngine()
        self._disposition_router = disposition_router or DispositionRouter()
        self._health_card_assembler = health_card_assembler or HealthCardAssembler()
        self._anomaly_threshold = anomaly_threshold

    async def execute(
        self, return_request: PipelineInput
    ) -> Union[HealthCard, PipelineError]:
        """Execute the full pipeline end-to-end.

        Steps:
        1. Run Grader (Anomaly + Wear + Intent) in parallel with Fraud Scanner
        2. Cross-validate penalties (use pessimistic signal)
        3. Compute health score
        4. Generate justification
        5. Check inconsistencies and aggregate fraud
        6. Route disposition
        7. Assemble Health Card

        Args:
            return_request: PipelineInput with all required data.

        Returns:
            HealthCard on success, PipelineError on complete failure.
        """
        pipeline_start = time.perf_counter()

        # Step 1: Parallel execution — Grader + Fraud Scanner
        grader_result, fraud_scan_result = await self._run_parallel(return_request)

        anomaly_result = grader_result["anomaly"]
        wear_result = grader_result["wear"]
        intent_result = grader_result["intent"]

        # Check for complete grader failure (Req 5.6)
        if self._is_complete_grader_failure(anomaly_result, wear_result, intent_result):
            return PipelineError(
                message="Grading could not be completed: all grader components failed.",
                failed_component="grader",
            )

        # Step 2: Cross-validation — use pessimistic signal (Req 21.1)
        authoritative_wear_penalty = self._cross_validator.cross_validate_penalty(
            qa_penalty=intent_result.return_reason_penalty,
            cv_penalty=wear_result.wear_detection_penalty,
        )

        # Step 3: Compute health score
        defect_penalty = anomaly_result.anomaly_severity  # normalized 0-1
        score_result = await self._health_score_computer.compute(
            anomaly_severity=anomaly_result.anomaly_severity,
            defect_penalty=defect_penalty,
            return_reason_penalty=intent_result.return_reason_penalty,
            wear_detection_penalty=authoritative_wear_penalty,
            category=return_request.category,
        )

        # Step 4: Generate justification
        defects = self._collect_defects(anomaly_result, wear_result)
        functional_pass = anomaly_result.anomaly_severity < self._anomaly_threshold
        justification = self._justification_engine.generate(
            condition=score_result.condition,
            defects=defects,
            anomaly_severity=anomaly_result.anomaly_severity,
            anomaly_threshold=self._anomaly_threshold,
            functional_pass=functional_pass,
            warranty_months=return_request.warranty_remaining_months,
        )

        # Step 5: Fraud aggregation
        # Check inconsistencies
        inconsistency_flags = self._intent_classifier.check_inconsistencies(
            qa_answers=return_request.qa_answers,
            wear_detection_penalty=wear_result.wear_detection_penalty,
        )

        # Compute behavioural score from inconsistency flags
        behavioural_score = self._compute_behavioural_score(inconsistency_flags)

        # Determine social signal
        social_signal: float | None = None
        social_scan_performed = False
        if fraud_scan_result is not None and fraud_scan_result.social_scan_performed:
            social_signal = fraud_scan_result.fraud_confidence
            social_scan_performed = True

        fraud_confidence = self._fraud_aggregator.aggregate(
            social_signal=social_signal,
            wear_penalty=wear_result.wear_detection_penalty,
            behavioural_score=behavioural_score,
            social_scan_performed=social_scan_performed,
        )

        # Escalate fraud if needed (Req 21.3)
        fraud_confidence = self._cross_validator.escalate_fraud(
            fraud_confidence=fraud_confidence,
            qa_answers=return_request.qa_answers,
            wear_detection_penalty=wear_result.wear_detection_penalty,
        )

        # Step 6: Disposition routing
        disposition_result = await self._disposition_router.route(
            health_score=score_result.health_score,
            fraud_confidence=fraud_confidence,
            category=return_request.category,
            qa_answers=return_request.qa_answers,
            product_value=return_request.product_value,
        )

        # Step 7: Assemble Health Card
        # Determine P2P eligibility
        p2p_offered = (
            fraud_confidence >= 0.60
            and return_request.category == FRAUD_SCAN_CATEGORY
        )
        customer_chose_p2p = False  # Default; set via separate API call

        health_card = self._health_card_assembler.assemble(
            score_result=score_result,
            anomaly_result=anomaly_result,
            fraud_confidence=fraud_confidence,
            disposition_result=disposition_result,
            justification=justification,
            fraud_scan_result=fraud_scan_result,
            p2p_offered=p2p_offered,
            customer_chose_p2p=customer_chose_p2p,
            warranty_months=return_request.warranty_remaining_months,
            defects=defects,
            category=return_request.category,
        )

        # Check total budget
        elapsed_ms = (time.perf_counter() - pipeline_start) * 1000
        if elapsed_ms > TOTAL_BUDGET_MS:
            logger.warning(
                "Pipeline exceeded 2000ms budget: %.1fms elapsed", elapsed_ms
            )

        return health_card

    async def _run_parallel(
        self, request: PipelineInput
    ) -> tuple[dict, FraudScanResult | None]:
        """Run Grader pipeline and Fraud Scanner in parallel.

        Grader: Anomaly + Wear + Intent (all run concurrently)
        Fraud Scanner: Only for Clothing & Footwear (Req 5.1, 5.2, 16.4)

        Returns:
            Tuple of (grader_results_dict, fraud_scan_result_or_None)
        """
        all_images = request.images + request.video_frames

        # Define grader tasks
        grader_task = self._run_grader(all_images, request)

        # Define fraud scanner task (only for Clothing & Footwear)
        if request.category == FRAUD_SCAN_CATEGORY:
            fraud_task = self._run_fraud_scanner(request)
        else:
            fraud_task = self._no_fraud_scan()

        # Execute in parallel (Req 5.1)
        grader_result, fraud_scan_result = await asyncio.gather(
            grader_task, fraud_task
        )

        return grader_result, fraud_scan_result

    async def _run_grader(
        self, all_images: list[np.ndarray], request: PipelineInput
    ) -> dict:
        """Run all grader sub-components in parallel with timeout handling.

        Components: Anomaly Detector, Wear Detector, Intent Classifier
        Each has a 5000ms hard timeout (Req 5.5).
        """
        anomaly_task = self._run_anomaly_detector(all_images, request.category)
        wear_task = self._run_wear_detector(request.images, request.category)
        intent_task = self._run_intent_classifier(
            request.qa_answers, request.category
        )

        anomaly_result, wear_result, intent_result = await asyncio.gather(
            anomaly_task, wear_task, intent_task
        )

        return {
            "anomaly": anomaly_result,
            "wear": wear_result,
            "intent": intent_result,
        }

    async def _run_anomaly_detector(
        self, images: list[np.ndarray], category: str
    ) -> AnomalyResult:
        """Run anomaly detector with 5s hard timeout.

        On failure: anomaly_severity=1.0 (worst case) per error handling strategy.
        """
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(self._anomaly_detector.detect, images, category),
                timeout=COMPONENT_HARD_TIMEOUT_S,
            )
            return result
        except asyncio.TimeoutError:
            logger.error("Anomaly detector timed out after 5000ms")
            return AnomalyResult(
                anomaly_severity=1.0,
                heatmap_uri="",
                model_available=False,
                failure_reason="component_timeout",
            )
        except Exception as e:
            logger.error("Anomaly detector failed: %s", str(e))
            return AnomalyResult(
                anomaly_severity=1.0,
                heatmap_uri="",
                model_available=False,
                failure_reason=str(e),
            )

    async def _run_wear_detector(
        self, images: list[np.ndarray], category: str
    ) -> WearResult:
        """Run wear detector with 5s hard timeout.

        On failure: wear_penalty=0.0, analysis_performed=False per error handling.
        """
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(self._wear_detector.detect, images, category),
                timeout=COMPONENT_HARD_TIMEOUT_S,
            )
            return result
        except asyncio.TimeoutError:
            logger.error("Wear detector timed out after 5000ms")
            return WearResult(
                wear_detection_penalty=0.0,
                wear_indicators=[],
                analysis_performed=False,
            )
        except Exception as e:
            logger.error("Wear detector failed: %s", str(e))
            return WearResult(
                wear_detection_penalty=0.0,
                wear_indicators=[],
                analysis_performed=False,
            )

    async def _run_intent_classifier(
        self, qa_answers: dict[str, str], category: str
    ) -> IntentResult:
        """Run intent classifier with 5s hard timeout.

        On failure: default medium penalty (0.15) per error handling.
        """
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    self._intent_classifier.classify, qa_answers, category
                ),
                timeout=COMPONENT_HARD_TIMEOUT_S,
            )
            return result
        except asyncio.TimeoutError:
            logger.error("Intent classifier timed out after 5000ms")
            return IntentResult(
                return_reason_penalty=0.15,
                penalty_category="medium",
                inconsistency_flags=[],
                unclassified=True,
            )
        except Exception as e:
            logger.error("Intent classifier failed: %s", str(e))
            return IntentResult(
                return_reason_penalty=0.15,
                penalty_category="medium",
                inconsistency_flags=[],
                unclassified=True,
            )

    async def _run_fraud_scanner(self, request: PipelineInput) -> FraudScanResult:
        """Run fraud scanner with 5s hard timeout.

        On failure: social_scan_performed=False per error handling.
        """
        from datetime import date

        try:
            purchase_date = date.fromisoformat(request.purchase_date)
            return_date = date.fromisoformat(request.return_date)
        except (ValueError, TypeError):
            purchase_date = date.today()
            return_date = date.today()

        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    self._fraud_scanner.scan,
                    customer_id=request.customer_id,
                    product_images=[],  # Catalog reference images not in PipelineInput
                    ownership_window=(purchase_date, return_date),
                    connected_accounts=request.connected_accounts,
                    category=request.category,
                ),
                timeout=COMPONENT_HARD_TIMEOUT_S,
            )
            return result
        except asyncio.TimeoutError:
            logger.error("Fraud scanner timed out after 5000ms")
            return FraudScanResult(
                social_scan_performed=False,
                accounts_scanned=[],
                product_found_in_social=False,
                fraud_confidence=0.0,
                evidence_posts=[],
                scan_window={},
            )
        except Exception as e:
            logger.error("Fraud scanner failed: %s", str(e))
            return FraudScanResult(
                social_scan_performed=False,
                accounts_scanned=[],
                product_found_in_social=False,
                fraud_confidence=0.0,
                evidence_posts=[],
                scan_window={},
            )

    async def _no_fraud_scan(self) -> FraudScanResult | None:
        """Return None when fraud scanning is not applicable (non-Clothing category)."""
        return None

    def _is_complete_grader_failure(
        self,
        anomaly_result: AnomalyResult,
        wear_result: WearResult,
        intent_result: IntentResult,
    ) -> bool:
        """Check if all grader components failed (Req 5.6).

        Complete grader failure = all three components have failure indicators:
        - Anomaly: failure_reason is set AND it's not just "no model available"
        - Wear: analysis_performed is False
        - Intent: unclassified is True

        A single surviving component still allows Health Card production.
        """
        anomaly_failed = (
            anomaly_result.failure_reason is not None
            and anomaly_result.failure_reason != "anomaly_model_unavailable"
            and anomaly_result.anomaly_severity == 1.0
        )
        wear_failed = not wear_result.analysis_performed
        intent_failed = intent_result.unclassified

        return anomaly_failed and wear_failed and intent_failed

    def _collect_defects(
        self, anomaly_result: AnomalyResult, wear_result: WearResult
    ) -> list[str]:
        """Collect defect descriptions from component results."""
        defects: list[str] = []

        # Record anomaly failure reasons as defects
        if anomaly_result.failure_reason:
            defects.append(anomaly_result.failure_reason)

        # Add wear indicators as defects
        for indicator in wear_result.wear_indicators:
            defects.append(indicator)

        return defects

    def _compute_behavioural_score(self, inconsistency_flags: list[str]) -> float:
        """Compute behavioural fraud score from inconsistency flags.

        Each flag contributes to a higher behavioural score.
        "never_used_but_wear_detected" is a strong signal.
        """
        if not inconsistency_flags:
            return 0.0

        # Each inconsistency flag adds 0.4 to the behavioural score
        score = len(inconsistency_flags) * 0.4
        return min(1.0, score)
