"""
Template Justification Engine service.

Generates human-readable justification strings from scoring pipeline outputs
using a template approach.

Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6
"""


class JustificationEngine:
    """Generates template-based justification strings from scoring outputs.

    Produces output in the format:
        "{condition}. Detected: {defects_list}. {anomaly_phrase}.
         Functional check: {pass_or_fail}. Warranty: {n} months remaining."

    All variable values are sourced directly from the scoring pipeline outputs.
    """

    def generate(
        self,
        condition: str,
        defects: list[str],
        anomaly_severity: float,
        anomaly_threshold: float,
        functional_pass: bool,
        warranty_months: int,
    ) -> str:
        """Generate a justification string from scoring outputs.

        Args:
            condition: Condition label ("Excellent", "Good", "Fair", "Poor").
            defects: List of defect descriptions with location.
            anomaly_severity: Anomaly severity score (0.0-1.0).
            anomaly_threshold: Configured anomaly threshold T for phrase mapping.
            functional_pass: Whether the item passed the functional check.
            warranty_months: Integer months of warranty remaining.

        Returns:
            Template-rendered justification string.
        """
        defects_list = self._format_defects(defects)
        anomaly_phrase = self._map_anomaly_phrase(anomaly_severity, anomaly_threshold)
        pass_or_fail = "pass" if functional_pass else "fail"

        return (
            f"{condition}. "
            f"Detected: {defects_list}. "
            f"{anomaly_phrase}. "
            f"Functional check: {pass_or_fail}. "
            f"Warranty: {warranty_months} months remaining."
        )

    @staticmethod
    def _format_defects(defects: list[str]) -> str:
        """Format the defects list for the justification string.

        Returns "none" if no defects, otherwise comma-separated defect names.
        """
        if not defects:
            return "none"
        return ", ".join(defects)

    @staticmethod
    def _map_anomaly_phrase(severity: float, threshold: float) -> str:
        """Map anomaly severity to a human-readable phrase.

        Phrase mapping based on severity relative to threshold T:
            - severity < T       → "No structural anomalies"
            - severity >= T and < 2T → "Minor anomalies detected"
            - severity >= 2T     → "Significant anomalies detected"

        Args:
            severity: Anomaly severity score (0.0-1.0).
            threshold: Configured anomaly threshold T.

        Returns:
            One of three fixed anomaly assessment phrases.
        """
        if severity < threshold:
            return "No structural anomalies"
        elif severity < 2 * threshold:
            return "Minor anomalies detected"
        else:
            return "Significant anomalies detected"
