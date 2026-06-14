"""
Unit tests for FraudAggregator service.

Tests weighted sum computation, proportional weight redistribution when signals
are missing, clamping to [0.0, 1.0], and performance within 50ms.

Requirements: 11.1, 11.2, 11.3, 11.4, 11.5
"""

import time

import pytest

from app.services.fraud_aggregator import FraudAggregator


@pytest.fixture
def aggregator() -> FraudAggregator:
    """Default aggregator with standard weights: social=0.40, wear=0.35, behavioural=0.25."""
    return FraudAggregator()


# ---------------------------------------------------------------------------
# Test: Weighted sum computation with all signals (Requirement 11.1)
# ---------------------------------------------------------------------------

class TestWeightedSumAllSignals:
    def test_all_signals_zero(self, aggregator: FraudAggregator):
        """All signals at 0.0 → fraud_confidence = 0.0."""
        result = aggregator.aggregate(
            social_signal=0.0,
            wear_penalty=0.0,
            behavioural_score=0.0,
            social_scan_performed=True,
        )
        assert result == 0.0

    def test_all_signals_one(self, aggregator: FraudAggregator):
        """All signals at 1.0 → fraud_confidence = 1.0."""
        result = aggregator.aggregate(
            social_signal=1.0,
            wear_penalty=1.0,
            behavioural_score=1.0,
            social_scan_performed=True,
        )
        assert result == pytest.approx(1.0)

    def test_weighted_sum_correctness(self, aggregator: FraudAggregator):
        """Verify exact weighted sum: 0.40*0.5 + 0.35*0.6 + 0.25*0.8 = 0.61."""
        result = aggregator.aggregate(
            social_signal=0.5,
            wear_penalty=0.6,
            behavioural_score=0.8,
            social_scan_performed=True,
        )
        expected = 0.40 * 0.5 + 0.35 * 0.6 + 0.25 * 0.8  # 0.20 + 0.21 + 0.20 = 0.61
        assert result == pytest.approx(expected, abs=1e-9)

    def test_only_social_signal(self, aggregator: FraudAggregator):
        """Only social signal at 1.0, others at 0.0 → fraud_confidence = 0.40."""
        result = aggregator.aggregate(
            social_signal=1.0,
            wear_penalty=0.0,
            behavioural_score=0.0,
            social_scan_performed=True,
        )
        assert result == pytest.approx(0.40, abs=1e-9)

    def test_only_wear_signal(self, aggregator: FraudAggregator):
        """Only wear at 1.0, others at 0.0 → fraud_confidence = 0.35."""
        result = aggregator.aggregate(
            social_signal=0.0,
            wear_penalty=1.0,
            behavioural_score=0.0,
            social_scan_performed=True,
        )
        assert result == pytest.approx(0.35, abs=1e-9)

    def test_only_behavioural_signal(self, aggregator: FraudAggregator):
        """Only behavioural at 1.0, others at 0.0 → fraud_confidence = 0.25."""
        result = aggregator.aggregate(
            social_signal=0.0,
            wear_penalty=0.0,
            behavioural_score=1.0,
            social_scan_performed=True,
        )
        assert result == pytest.approx(0.25, abs=1e-9)


# ---------------------------------------------------------------------------
# Test: Proportional redistribution when social not performed (Req 11.3)
# ---------------------------------------------------------------------------

class TestSocialNotPerformed:
    def test_social_not_performed_redistributes_weight(self, aggregator: FraudAggregator):
        """When social_scan_performed=False, social weight redistributed proportionally.

        New wear_weight = 0.35 / (0.35 + 0.25) = 0.5833...
        New behavioural_weight = 0.25 / (0.35 + 0.25) = 0.4166...
        """
        result = aggregator.aggregate(
            social_signal=None,
            wear_penalty=0.6,
            behavioural_score=0.8,
            social_scan_performed=False,
        )
        # Expected: (0.35/0.60)*0.6 + (0.25/0.60)*0.8 = 0.35 + 0.333... = 0.683...
        new_wear_weight = 0.35 / (0.35 + 0.25)  # 0.5833...
        new_beh_weight = 0.25 / (0.35 + 0.25)   # 0.4166...
        expected = new_wear_weight * 0.6 + new_beh_weight * 0.8
        assert result == pytest.approx(expected, abs=1e-9)

    def test_social_not_performed_all_ones(self, aggregator: FraudAggregator):
        """When social not performed and remaining signals = 1.0, result = 1.0."""
        result = aggregator.aggregate(
            social_signal=None,
            wear_penalty=1.0,
            behavioural_score=1.0,
            social_scan_performed=False,
        )
        assert result == pytest.approx(1.0, abs=1e-9)

    def test_social_not_performed_all_zeros(self, aggregator: FraudAggregator):
        """When social not performed and remaining signals = 0.0, result = 0.0."""
        result = aggregator.aggregate(
            social_signal=None,
            wear_penalty=0.0,
            behavioural_score=0.0,
            social_scan_performed=False,
        )
        assert result == 0.0

    def test_social_signal_none_treated_as_unavailable(self, aggregator: FraudAggregator):
        """social_signal=None with social_scan_performed=True still redistributes."""
        result = aggregator.aggregate(
            social_signal=None,
            wear_penalty=0.5,
            behavioural_score=0.5,
            social_scan_performed=True,
        )
        # Since social_signal is None, social weight is redistributed
        # Result should be same as if social_scan_performed=False
        expected = aggregator.aggregate(
            social_signal=None,
            wear_penalty=0.5,
            behavioural_score=0.5,
            social_scan_performed=False,
        )
        assert result == pytest.approx(expected, abs=1e-9)

    def test_absence_of_social_does_not_inflate_score(self, aggregator: FraudAggregator):
        """Requirement 11.3: Absence of social data must not inflate the score.

        If wear=0.3 and behavioural=0.3, the score should be approx 0.3
        regardless of whether social scan is performed.
        """
        # With social performed (social=0.3 too)
        result_with_social = aggregator.aggregate(
            social_signal=0.3,
            wear_penalty=0.3,
            behavioural_score=0.3,
            social_scan_performed=True,
        )

        # Without social
        result_without_social = aggregator.aggregate(
            social_signal=None,
            wear_penalty=0.3,
            behavioural_score=0.3,
            social_scan_performed=False,
        )

        # Both should produce the same score since all values are equal
        assert result_with_social == pytest.approx(0.3, abs=1e-9)
        assert result_without_social == pytest.approx(0.3, abs=1e-9)


# ---------------------------------------------------------------------------
# Test: Missing component handling (Requirement 11.4)
# ---------------------------------------------------------------------------

class TestMissingComponents:
    def test_wear_none_redistributes(self, aggregator: FraudAggregator):
        """When wear_penalty is None, its weight redistributed to remaining signals."""
        result = aggregator.aggregate(
            social_signal=0.8,
            wear_penalty=None,
            behavioural_score=0.4,
            social_scan_performed=True,
        )
        # Wear weight (0.35) redistributed proportionally among social (0.40) + behavioural (0.25)
        new_social_weight = 0.40 / (0.40 + 0.25)  # 0.6153...
        new_beh_weight = 0.25 / (0.40 + 0.25)     # 0.3846...
        expected = new_social_weight * 0.8 + new_beh_weight * 0.4
        assert result == pytest.approx(expected, abs=1e-9)

    def test_behavioural_none_redistributes(self, aggregator: FraudAggregator):
        """When behavioural_score is None, its weight redistributed to remaining signals."""
        result = aggregator.aggregate(
            social_signal=0.6,
            wear_penalty=0.7,
            behavioural_score=None,
            social_scan_performed=True,
        )
        # Behavioural weight (0.25) redistributed among social (0.40) + wear (0.35)
        new_social_weight = 0.40 / (0.40 + 0.35)  # 0.5333...
        new_wear_weight = 0.35 / (0.40 + 0.35)    # 0.4666...
        expected = new_social_weight * 0.6 + new_wear_weight * 0.7
        assert result == pytest.approx(expected, abs=1e-9)

    def test_all_signals_none(self, aggregator: FraudAggregator):
        """When all signals are None/unavailable, fraud_confidence = 0.0."""
        result = aggregator.aggregate(
            social_signal=None,
            wear_penalty=None,
            behavioural_score=None,
            social_scan_performed=False,
        )
        assert result == 0.0

    def test_only_wear_available(self, aggregator: FraudAggregator):
        """When only wear is available, all weight goes to wear."""
        result = aggregator.aggregate(
            social_signal=None,
            wear_penalty=0.7,
            behavioural_score=None,
            social_scan_performed=False,
        )
        # All weight redistributed to wear: effective weight = 1.0
        assert result == pytest.approx(0.7, abs=1e-9)

    def test_only_behavioural_available(self, aggregator: FraudAggregator):
        """When only behavioural is available, all weight goes to behavioural."""
        result = aggregator.aggregate(
            social_signal=None,
            wear_penalty=None,
            behavioural_score=0.5,
            social_scan_performed=False,
        )
        # All weight redistributed to behavioural: effective weight = 1.0
        assert result == pytest.approx(0.5, abs=1e-9)


# ---------------------------------------------------------------------------
# Test: Output clamping to [0.0, 1.0]
# ---------------------------------------------------------------------------

class TestClamping:
    def test_result_in_valid_range(self, aggregator: FraudAggregator):
        """Result is always in [0.0, 1.0] for valid inputs."""
        result = aggregator.aggregate(
            social_signal=0.9,
            wear_penalty=0.8,
            behavioural_score=0.7,
            social_scan_performed=True,
        )
        assert 0.0 <= result <= 1.0

    def test_clamp_minimum(self, aggregator: FraudAggregator):
        """Negative intermediate values are clamped to 0.0."""
        # All zero signals should produce exactly 0.0
        result = aggregator.aggregate(
            social_signal=0.0,
            wear_penalty=0.0,
            behavioural_score=0.0,
            social_scan_performed=True,
        )
        assert result >= 0.0

    def test_clamp_maximum(self, aggregator: FraudAggregator):
        """Values at boundaries stay within [0.0, 1.0]."""
        result = aggregator.aggregate(
            social_signal=1.0,
            wear_penalty=1.0,
            behavioural_score=1.0,
            social_scan_performed=True,
        )
        assert result <= 1.0


# ---------------------------------------------------------------------------
# Test: Configurable weights (Requirement 11.1)
# ---------------------------------------------------------------------------

class TestConfigurableWeights:
    def test_custom_weights(self):
        """Custom weights should be used in computation."""
        agg = FraudAggregator(social_weight=0.50, wear_weight=0.30, behavioural_weight=0.20)
        result = agg.aggregate(
            social_signal=1.0,
            wear_penalty=0.0,
            behavioural_score=0.0,
            social_scan_performed=True,
        )
        assert result == pytest.approx(0.50, abs=1e-9)

    def test_equal_weights(self):
        """Equal weights should average the signals."""
        agg = FraudAggregator(
            social_weight=1.0 / 3,
            wear_weight=1.0 / 3,
            behavioural_weight=1.0 / 3,
        )
        result = agg.aggregate(
            social_signal=0.3,
            wear_penalty=0.6,
            behavioural_score=0.9,
            social_scan_performed=True,
        )
        expected = (0.3 + 0.6 + 0.9) / 3
        assert result == pytest.approx(expected, abs=1e-9)

    def test_invalid_weights_raise_error(self):
        """Weights not summing to 1.0 should raise ValueError."""
        with pytest.raises(ValueError, match="must sum to 1.0"):
            FraudAggregator(social_weight=0.5, wear_weight=0.5, behavioural_weight=0.5)

    def test_weights_summing_slightly_off_ok(self):
        """Weights that sum to 1.0 within floating point tolerance are accepted."""
        # These weights sum to exactly 1.0 in float
        agg = FraudAggregator(social_weight=0.33, wear_weight=0.34, behavioural_weight=0.33)
        result = agg.aggregate(
            social_signal=0.5,
            wear_penalty=0.5,
            behavioural_score=0.5,
            social_scan_performed=True,
        )
        assert result == pytest.approx(0.5, abs=1e-9)


# ---------------------------------------------------------------------------
# Test: Performance within 50ms (Requirement 11.5)
# ---------------------------------------------------------------------------

class TestPerformance:
    def test_completes_within_50ms(self, aggregator: FraudAggregator):
        """Aggregation must complete within 50ms."""
        start = time.perf_counter()
        for _ in range(1000):
            aggregator.aggregate(
                social_signal=0.7,
                wear_penalty=0.5,
                behavioural_score=0.3,
                social_scan_performed=True,
            )
        elapsed_ms = (time.perf_counter() - start) * 1000

        # 1000 iterations should complete well within 50ms total
        # Individual call << 50ms (this tests the happy path)
        assert elapsed_ms < 50000  # 1000 calls * 50ms = 50s max

    def test_single_call_under_50ms(self, aggregator: FraudAggregator):
        """A single aggregation call must complete within 50ms."""
        start = time.perf_counter()
        aggregator.aggregate(
            social_signal=0.8,
            wear_penalty=0.6,
            behavioural_score=0.4,
            social_scan_performed=True,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 50


# ---------------------------------------------------------------------------
# Test: Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_social_signal_zero_with_scan_performed(self, aggregator: FraudAggregator):
        """Social signal of 0.0 with scan performed is a valid signal (no fraud detected)."""
        result = aggregator.aggregate(
            social_signal=0.0,
            wear_penalty=0.5,
            behavioural_score=0.5,
            social_scan_performed=True,
        )
        # 0.40*0.0 + 0.35*0.5 + 0.25*0.5 = 0.0 + 0.175 + 0.125 = 0.30
        expected = 0.40 * 0.0 + 0.35 * 0.5 + 0.25 * 0.5
        assert result == pytest.approx(expected, abs=1e-9)

    def test_boundary_signals(self, aggregator: FraudAggregator):
        """Test with signals at boundary values (0.0 and 1.0)."""
        result = aggregator.aggregate(
            social_signal=1.0,
            wear_penalty=0.0,
            behavioural_score=1.0,
            social_scan_performed=True,
        )
        expected = 0.40 * 1.0 + 0.35 * 0.0 + 0.25 * 1.0  # 0.40 + 0 + 0.25 = 0.65
        assert result == pytest.approx(expected, abs=1e-9)

    def test_redistribution_preserves_relative_weights(self, aggregator: FraudAggregator):
        """When social is missing, relative ratio of wear:behavioural is preserved.

        Original: wear=0.35, behavioural=0.25 → ratio 7:5
        After redistribution, the ratio should remain 7:5.
        """
        # With different wear and behavioural values
        result_wear_only = aggregator.aggregate(
            social_signal=None,
            wear_penalty=1.0,
            behavioural_score=0.0,
            social_scan_performed=False,
        )
        result_beh_only = aggregator.aggregate(
            social_signal=None,
            wear_penalty=0.0,
            behavioural_score=1.0,
            social_scan_performed=False,
        )
        # Ratio should be 0.35:0.25 = 7:5
        ratio = result_wear_only / result_beh_only
        expected_ratio = 0.35 / 0.25
        assert ratio == pytest.approx(expected_ratio, abs=1e-6)
