"""
Unit tests for the Template Justification Engine.

Tests cover:
- Template output format correctness
- Anomaly phrase mapping based on severity vs threshold
- Defect list formatting (including empty defects)
- Functional check pass/fail rendering
- Warranty months rendering

Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6
"""

import pytest

from app.services.justification import JustificationEngine


@pytest.fixture
def engine():
    return JustificationEngine()


class TestGenerateTemplateFormat:
    """Test that the generate method produces the correct template format."""

    def test_basic_template_structure(self, engine: JustificationEngine):
        """Verify the full template structure with all components."""
        result = engine.generate(
            condition="Good",
            defects=["minor scratch (rear casing)"],
            anomaly_severity=0.1,
            anomaly_threshold=0.3,
            functional_pass=True,
            warranty_months=5,
        )
        expected = (
            "Good. Detected: minor scratch (rear casing). "
            "No structural anomalies. "
            "Functional check: pass. "
            "Warranty: 5 months remaining."
        )
        assert result == expected

    def test_excellent_condition_with_no_defects(self, engine: JustificationEngine):
        """Verify Excellent condition with empty defects list."""
        result = engine.generate(
            condition="Excellent",
            defects=[],
            anomaly_severity=0.0,
            anomaly_threshold=0.3,
            functional_pass=True,
            warranty_months=12,
        )
        expected = (
            "Excellent. Detected: none. "
            "No structural anomalies. "
            "Functional check: pass. "
            "Warranty: 12 months remaining."
        )
        assert result == expected

    def test_poor_condition_with_multiple_defects(self, engine: JustificationEngine):
        """Verify Poor condition with multiple defects and significant anomalies."""
        result = engine.generate(
            condition="Poor",
            defects=["cracked screen (front)", "dent (top corner)", "scratches (back panel)"],
            anomaly_severity=0.8,
            anomaly_threshold=0.3,
            functional_pass=False,
            warranty_months=0,
        )
        expected = (
            "Poor. Detected: cracked screen (front), dent (top corner), scratches (back panel). "
            "Significant anomalies detected. "
            "Functional check: fail. "
            "Warranty: 0 months remaining."
        )
        assert result == expected

    def test_fair_condition_with_minor_anomalies(self, engine: JustificationEngine):
        """Verify Fair condition with minor anomalies phrase."""
        result = engine.generate(
            condition="Fair",
            defects=["fabric stress (collar)"],
            anomaly_severity=0.4,
            anomaly_threshold=0.3,
            functional_pass=True,
            warranty_months=3,
        )
        expected = (
            "Fair. Detected: fabric stress (collar). "
            "Minor anomalies detected. "
            "Functional check: pass. "
            "Warranty: 3 months remaining."
        )
        assert result == expected


class TestAnomalyPhraseMapping:
    """Test the anomaly phrase mapping logic against threshold T."""

    def test_severity_below_threshold(self, engine: JustificationEngine):
        """severity < T → 'No structural anomalies'"""
        result = engine.generate(
            condition="Good", defects=[], anomaly_severity=0.1,
            anomaly_threshold=0.3, functional_pass=True, warranty_months=6,
        )
        assert "No structural anomalies" in result

    def test_severity_at_threshold(self, engine: JustificationEngine):
        """severity == T → 'Minor anomalies detected' (>= T and < 2T)"""
        result = engine.generate(
            condition="Good", defects=[], anomaly_severity=0.3,
            anomaly_threshold=0.3, functional_pass=True, warranty_months=6,
        )
        assert "Minor anomalies detected" in result

    def test_severity_between_t_and_2t(self, engine: JustificationEngine):
        """T <= severity < 2T → 'Minor anomalies detected'"""
        result = engine.generate(
            condition="Good", defects=[], anomaly_severity=0.5,
            anomaly_threshold=0.3, functional_pass=True, warranty_months=6,
        )
        assert "Minor anomalies detected" in result

    def test_severity_at_2t(self, engine: JustificationEngine):
        """severity == 2T → 'Significant anomalies detected'"""
        result = engine.generate(
            condition="Good", defects=[], anomaly_severity=0.6,
            anomaly_threshold=0.3, functional_pass=True, warranty_months=6,
        )
        assert "Significant anomalies detected" in result

    def test_severity_above_2t(self, engine: JustificationEngine):
        """severity > 2T → 'Significant anomalies detected'"""
        result = engine.generate(
            condition="Good", defects=[], anomaly_severity=0.9,
            anomaly_threshold=0.3, functional_pass=True, warranty_months=6,
        )
        assert "Significant anomalies detected" in result

    def test_zero_severity_with_nonzero_threshold(self, engine: JustificationEngine):
        """severity=0.0 with any positive threshold → 'No structural anomalies'"""
        result = engine.generate(
            condition="Excellent", defects=[], anomaly_severity=0.0,
            anomaly_threshold=0.5, functional_pass=True, warranty_months=10,
        )
        assert "No structural anomalies" in result

    def test_small_threshold_boundary(self, engine: JustificationEngine):
        """Verify boundaries with a very small threshold."""
        # severity=0.09, T=0.05: 0.09 < 0.10 (2T) → Minor
        result = engine.generate(
            condition="Good", defects=[], anomaly_severity=0.09,
            anomaly_threshold=0.05, functional_pass=True, warranty_months=6,
        )
        assert "Minor anomalies detected" in result

        # severity=0.10, T=0.05: 0.10 >= 0.10 (2T) → Significant
        result = engine.generate(
            condition="Good", defects=[], anomaly_severity=0.10,
            anomaly_threshold=0.05, functional_pass=True, warranty_months=6,
        )
        assert "Significant anomalies detected" in result


class TestDefectFormatting:
    """Test defect list formatting in the justification output."""

    def test_empty_defects_renders_none(self, engine: JustificationEngine):
        """Empty defects list → 'Detected: none'"""
        result = engine.generate(
            condition="Excellent", defects=[], anomaly_severity=0.0,
            anomaly_threshold=0.3, functional_pass=True, warranty_months=6,
        )
        assert "Detected: none." in result

    def test_single_defect(self, engine: JustificationEngine):
        """Single defect renders correctly."""
        result = engine.generate(
            condition="Good", defects=["scratch on back"], anomaly_severity=0.1,
            anomaly_threshold=0.3, functional_pass=True, warranty_months=6,
        )
        assert "Detected: scratch on back." in result

    def test_multiple_defects_comma_separated(self, engine: JustificationEngine):
        """Multiple defects are comma-separated."""
        defects = ["scratch (back)", "dent (top)", "stain (front)"]
        result = engine.generate(
            condition="Fair", defects=defects, anomaly_severity=0.1,
            anomaly_threshold=0.3, functional_pass=True, warranty_months=2,
        )
        assert "Detected: scratch (back), dent (top), stain (front)." in result


class TestFunctionalCheck:
    """Test functional check pass/fail rendering."""

    def test_functional_pass_true(self, engine: JustificationEngine):
        """functional_pass=True → 'Functional check: pass'"""
        result = engine.generate(
            condition="Good", defects=[], anomaly_severity=0.1,
            anomaly_threshold=0.3, functional_pass=True, warranty_months=6,
        )
        assert "Functional check: pass." in result

    def test_functional_pass_false(self, engine: JustificationEngine):
        """functional_pass=False → 'Functional check: fail'"""
        result = engine.generate(
            condition="Poor", defects=["broken screen"], anomaly_severity=0.8,
            anomaly_threshold=0.3, functional_pass=False, warranty_months=0,
        )
        assert "Functional check: fail." in result


class TestWarrantyMonths:
    """Test warranty months rendering in the justification."""

    def test_zero_warranty(self, engine: JustificationEngine):
        """Zero warranty months renders correctly."""
        result = engine.generate(
            condition="Poor", defects=[], anomaly_severity=0.8,
            anomaly_threshold=0.3, functional_pass=False, warranty_months=0,
        )
        assert "Warranty: 0 months remaining." in result

    def test_positive_warranty(self, engine: JustificationEngine):
        """Positive warranty months renders as integer."""
        result = engine.generate(
            condition="Good", defects=[], anomaly_severity=0.1,
            anomaly_threshold=0.3, functional_pass=True, warranty_months=11,
        )
        assert "Warranty: 11 months remaining." in result

    def test_large_warranty(self, engine: JustificationEngine):
        """Large warranty value renders correctly."""
        result = engine.generate(
            condition="Excellent", defects=[], anomaly_severity=0.0,
            anomaly_threshold=0.3, functional_pass=True, warranty_months=24,
        )
        assert "Warranty: 24 months remaining." in result


class TestConditionLabels:
    """Test that all condition labels render correctly in the output."""

    @pytest.mark.parametrize("condition", ["Excellent", "Good", "Fair", "Poor"])
    def test_condition_label_appears_at_start(self, engine: JustificationEngine, condition: str):
        """Each condition label appears at the start of the justification."""
        result = engine.generate(
            condition=condition, defects=[], anomaly_severity=0.1,
            anomaly_threshold=0.3, functional_pass=True, warranty_months=6,
        )
        assert result.startswith(f"{condition}.")
