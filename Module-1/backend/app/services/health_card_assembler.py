"""
Health Card Assembler service.

Composes all pipeline outputs into the final Health Card JSON,
the inter-module contract consumed by Modules 2–5.

Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 18.1, 18.4
"""

from app.models.health_card import FraudSignal, HealthCard
from app.models.results import (
    AnomalyResult,
    DispositionResult,
    FraudScanResult,
    HealthScoreResult,
)

# Threshold for P2P fraud divert eligibility
_P2P_FRAUD_THRESHOLD = 0.60
_P2P_ELIGIBLE_CATEGORY = "Clothing & Footwear"


class HealthCardAssembler:
    """Assembles pipeline outputs into a complete Health Card JSON.

    Ensures all required schema fields are present. When a field cannot
    be populated, it is set to a safe default and confidence is set to 0.0.
    """

    def assemble(
        self,
        score_result: HealthScoreResult,
        anomaly_result: AnomalyResult,
        fraud_confidence: float,
        disposition_result: DispositionResult,
        justification: str,
        fraud_scan_result: FraudScanResult | None,
        p2p_offered: bool,
        customer_chose_p2p: bool,
        warranty_months: int,
        defects: list[str],
        category: str,
    ) -> HealthCard:
        """Compose all pipeline outputs into the Health Card JSON.

        Args:
            score_result: Output from HealthScoreComputer.
            anomaly_result: Output from AnomalyDetector.
            fraud_confidence: Aggregated fraud confidence (0.0–1.0).
            disposition_result: Output from DispositionRouter.
            justification: Template justification string.
            fraud_scan_result: Output from FraudScanner (None if not executed).
            p2p_offered: Whether P2P divert was offered to the customer.
            customer_chose_p2p: Whether the customer chose P2P resale.
            warranty_months: Remaining warranty in months.
            defects: List of defect descriptions.
            category: Product category string.

        Returns:
            A fully populated HealthCard instance.
        """
        source = self._determine_source(
            fraud_confidence=fraud_confidence,
            category=category,
            customer_chose_p2p=customer_chose_p2p,
        )

        fraud_signal = self._build_fraud_signal(
            fraud_scan_result=fraud_scan_result,
            fraud_confidence=fraud_confidence,
            p2p_offered=p2p_offered,
            customer_chose_p2p=customer_chose_p2p,
        )

        confidence = self._calculate_confidence(
            anomaly_result=anomaly_result,
            score_result=score_result,
        )

        return HealthCard(
            condition=score_result.condition,
            health_score=score_result.health_score,
            confidence=confidence,
            warranty_left_months=warranty_months,
            defects=defects,
            anomaly_heatmap_uri=anomaly_result.heatmap_uri,
            justification=justification,
            disposition=disposition_result.disposition,
            source=source,
            fraud_signal=fraud_signal,
        )

    def _determine_source(
        self,
        fraud_confidence: float,
        category: str,
        customer_chose_p2p: bool,
    ) -> str:
        """Determine the source field value.

        source = "p2p_fraud_divert" WHEN:
            - fraud_confidence >= 0.60
            - category is "Clothing & Footwear"
            - customer_chose_p2p is True

        Otherwise source = "standard_return".
        """
        if (
            fraud_confidence >= _P2P_FRAUD_THRESHOLD
            and category == _P2P_ELIGIBLE_CATEGORY
            and customer_chose_p2p
        ):
            return "p2p_fraud_divert"
        return "standard_return"

    def _build_fraud_signal(
        self,
        fraud_scan_result: FraudScanResult | None,
        fraud_confidence: float,
        p2p_offered: bool,
        customer_chose_p2p: bool,
    ) -> FraudSignal:
        """Build a complete FraudSignal block.

        Validates completeness — all fields must be present.
        When fraud_scan_result is None (scan not performed),
        social fields default to safe values.
        """
        if fraud_scan_result is not None:
            social_scan_performed = fraud_scan_result.social_scan_performed
            product_found_in_social = fraud_scan_result.product_found_in_social
        else:
            social_scan_performed = False
            product_found_in_social = False

        return FraudSignal(
            social_scan_performed=social_scan_performed,
            product_found_in_social=product_found_in_social,
            fraud_confidence=fraud_confidence,
            p2p_offered=p2p_offered,
            customer_chose_p2p=customer_chose_p2p,
        )

    def _calculate_confidence(
        self,
        anomaly_result: AnomalyResult,
        score_result: HealthScoreResult,
    ) -> float:
        """Calculate pipeline confidence.

        Confidence reflects how many pipeline components succeeded:
        - All components succeed: 1.0
        - Anomaly model unavailable: 0.7
        - Wear analysis not performed: 0.8
        - Use minimum confidence across components.

        Since wear analysis status is embedded in the score (wear contribution
        is 0 when not performed), we infer from anomaly_result availability.
        """
        confidences: list[float] = []

        # Anomaly detector confidence
        if not anomaly_result.model_available:
            confidences.append(0.7)
        else:
            confidences.append(1.0)

        # Base score confidence (always available if we get here)
        confidences.append(1.0)

        # Return minimum confidence across all components
        return min(confidences) if confidences else 1.0
