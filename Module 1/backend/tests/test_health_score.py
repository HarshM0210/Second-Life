"""Unit tests for HealthScoreComputer service."""

import os

import pytest
import pytest_asyncio

from app.config.database import init_db
from app.models.results import HealthScoreResult, ScoreBreakdownResult
from app.services.health_score import HealthScoreComputer

TEST_DB = "test_health_score.db"


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db(monkeypatch):
    """Use a temporary test database with seeded category weights."""
    monkeypatch.setattr("app.config.database.DATABASE_PATH", TEST_DB)
    monkeypatch.setattr("app.services.health_score.DATABASE_PATH", TEST_DB)
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    await init_db()
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


@pytest.fixture
def computer():
    return HealthScoreComputer()


# --- Formula correctness tests ---


@pytest.mark.asyncio
async def test_perfect_score_all_zeros(computer):
    """All zero penalties should yield health_score = 100."""
    result = await computer.compute(0.0, 0.0, 0.0, 0.0, "Electronics")

    assert result.health_score == 100
    assert result.condition == "Excellent"
    assert result.breakdown.w1_anomaly_contribution == 0.0
    assert result.breakdown.w2_defect_contribution == 0.0
    assert result.breakdown.w3_reason_contribution == 0.0
    assert result.breakdown.w4_wear_contribution == 0.0


@pytest.mark.asyncio
async def test_worst_score_all_ones(computer):
    """All max penalties should yield health_score = 0."""
    result = await computer.compute(1.0, 1.0, 1.0, 1.0, "Electronics")

    # Electronics weights: 30 + 25 + 25 + 20 = 100, so 100 - 100 = 0
    assert result.health_score == 0
    assert result.condition == "Poor"


@pytest.mark.asyncio
async def test_electronics_weighted_formula(computer):
    """Electronics: weights (30, 25, 25, 20). Verify formula."""
    # anomaly=0.5, defect=0.2, reason=0.3, wear=0.1
    # 100 - (30*0.5 + 25*0.2 + 25*0.3 + 20*0.1)
    # 100 - (15 + 5 + 7.5 + 2) = 100 - 29.5 = 70.5 → 70
    result = await computer.compute(0.5, 0.2, 0.3, 0.1, "Electronics")

    assert result.health_score == 70
    assert result.condition == "Fair"


@pytest.mark.asyncio
async def test_food_grocery_weights(computer):
    """Food & Grocery: weights (20, 30, 30, 20)."""
    # anomaly=0.1, defect=0.1, reason=0.1, wear=0.1
    # 100 - (20*0.1 + 30*0.1 + 30*0.1 + 20*0.1)
    # 100 - (2 + 3 + 3 + 2) = 100 - 10 = 90
    result = await computer.compute(0.1, 0.1, 0.1, 0.1, "Food & Grocery")

    assert result.health_score == 90
    assert result.condition == "Good"


@pytest.mark.asyncio
async def test_clothing_footwear_weights(computer):
    """Clothing & Footwear: weights (20, 20, 20, 40). Wear is heaviest."""
    # anomaly=0.0, defect=0.0, reason=0.0, wear=0.5
    # 100 - (20*0 + 20*0 + 20*0 + 40*0.5) = 100 - 20 = 80
    result = await computer.compute(0.0, 0.0, 0.0, 0.5, "Clothing & Footwear")

    assert result.health_score == 80
    assert result.condition == "Good"


@pytest.mark.asyncio
async def test_other_category_equal_weights(computer):
    """Other: weights (25, 25, 25, 25). All equal."""
    # All 0.4 → 100 - (25*0.4 * 4) = 100 - 40 = 60
    result = await computer.compute(0.4, 0.4, 0.4, 0.4, "Other")

    assert result.health_score == 60
    assert result.condition == "Fair"


# --- Clamping tests ---


@pytest.mark.asyncio
async def test_clamped_to_zero(computer):
    """Score below 0 is clamped to 0."""
    # With Other category (25, 25, 25, 25) and all 1.0:
    # 100 - 100 = 0, already at boundary
    # Use higher values scenario by testing result is minimum 0
    result = await computer.compute(1.0, 1.0, 1.0, 1.0, "Other")

    assert result.health_score == 0
    assert result.condition == "Poor"


@pytest.mark.asyncio
async def test_clamped_to_100(computer):
    """Score above 100 is clamped to 100 (only possible with all 0 penalties)."""
    result = await computer.compute(0.0, 0.0, 0.0, 0.0, "Other")

    assert result.health_score == 100
    assert result.condition == "Excellent"


# --- Condition mapping tests ---


@pytest.mark.asyncio
async def test_condition_excellent_boundary(computer):
    """Score of exactly 91 maps to Excellent."""
    # Other weights (25,25,25,25). Need total penalty = 9.
    # 9/100 = 0.09 across all, but we need exactly 9.
    # 25*x*4 = 9 → x = 0.09
    result = await computer.compute(0.09, 0.09, 0.09, 0.09, "Other")
    # 100 - (25*0.09*4) = 100 - 9 = 91
    assert result.health_score == 91
    assert result.condition == "Excellent"


@pytest.mark.asyncio
async def test_condition_good_at_90(computer):
    """Score of exactly 90 maps to Good (not Excellent, since >90 is Excellent)."""
    # 25*x*4 = 10 → x = 0.1
    result = await computer.compute(0.1, 0.1, 0.1, 0.1, "Other")
    # 100 - 10 = 90
    assert result.health_score == 90
    assert result.condition == "Good"


@pytest.mark.asyncio
async def test_condition_good_at_71(computer):
    """Score of 71 maps to Good."""
    # 25*x*4 = 29 → x = 0.29
    result = await computer.compute(0.29, 0.29, 0.29, 0.29, "Other")
    # 100 - (25*0.29*4) = 100 - 29 = 71
    assert result.health_score == 71
    assert result.condition == "Good"


@pytest.mark.asyncio
async def test_condition_fair_at_70(computer):
    """Score of exactly 70 maps to Fair (not Good, since >70 is Good)."""
    # 25*x*4 = 30 → x = 0.3
    result = await computer.compute(0.3, 0.3, 0.3, 0.3, "Other")
    # 100 - 30 = 70
    assert result.health_score == 70
    assert result.condition == "Fair"


@pytest.mark.asyncio
async def test_condition_fair_at_51(computer):
    """Score of 51 maps to Fair."""
    # 25*x*4 = 49 → x = 0.49
    result = await computer.compute(0.49, 0.49, 0.49, 0.49, "Other")
    # 100 - 49 = 51
    assert result.health_score == 51
    assert result.condition == "Fair"


@pytest.mark.asyncio
async def test_condition_poor_at_50(computer):
    """Score of exactly 50 maps to Poor (<=50 is Poor)."""
    # 25*x*4 = 50 → x = 0.5
    result = await computer.compute(0.5, 0.5, 0.5, 0.5, "Other")
    # 100 - 50 = 50
    assert result.health_score == 50
    assert result.condition == "Poor"


@pytest.mark.asyncio
async def test_condition_poor_at_zero(computer):
    """Score of 0 maps to Poor."""
    result = await computer.compute(1.0, 1.0, 1.0, 1.0, "Other")

    assert result.health_score == 0
    assert result.condition == "Poor"


# --- Unknown category / fallback tests ---


@pytest.mark.asyncio
async def test_unknown_category_uses_default_weights(computer):
    """Unknown category falls back to equal weights (25, 25, 25, 25)."""
    result = await computer.compute(0.2, 0.2, 0.2, 0.2, "Unknown Category")
    # 100 - (25*0.2*4) = 100 - 20 = 80
    assert result.health_score == 80
    assert result.condition == "Good"


# --- Breakdown correctness tests ---


@pytest.mark.asyncio
async def test_breakdown_values_correct(computer):
    """Verify breakdown contains correct weighted contributions."""
    result = await computer.compute(0.5, 0.3, 0.2, 0.8, "Electronics")
    # Electronics: (30, 25, 25, 20)
    # w1: 30*0.5=15, w2: 25*0.3=7.5, w3: 25*0.2=5, w4: 20*0.8=16

    assert result.breakdown.w1_anomaly_contribution == pytest.approx(15.0)
    assert result.breakdown.w2_defect_contribution == pytest.approx(7.5)
    assert result.breakdown.w3_reason_contribution == pytest.approx(5.0)
    assert result.breakdown.w4_wear_contribution == pytest.approx(16.0)


@pytest.mark.asyncio
async def test_breakdown_sum_equals_total_penalty(computer):
    """Sum of breakdown contributions should equal (100 - health_score) when not clamped."""
    result = await computer.compute(0.3, 0.2, 0.4, 0.1, "Electronics")
    # 30*0.3 + 25*0.2 + 25*0.4 + 20*0.1 = 9 + 5 + 10 + 2 = 26
    # health_score = 100 - 26 = 74

    total_penalty = (
        result.breakdown.w1_anomaly_contribution
        + result.breakdown.w2_defect_contribution
        + result.breakdown.w3_reason_contribution
        + result.breakdown.w4_wear_contribution
    )
    assert total_penalty == pytest.approx(100 - result.health_score)


# --- Result type tests ---


@pytest.mark.asyncio
async def test_result_is_correct_dataclass(computer):
    """Validate that the result is a proper HealthScoreResult instance."""
    result = await computer.compute(0.1, 0.2, 0.3, 0.4, "Electronics")

    assert isinstance(result, HealthScoreResult)
    assert isinstance(result.breakdown, ScoreBreakdownResult)
    assert isinstance(result.health_score, int)
    assert result.condition in ("Excellent", "Good", "Fair", "Poor")


# --- Database fallback test ---


@pytest.mark.asyncio
async def test_db_failure_uses_default_weights(computer, monkeypatch):
    """If the database is unreachable, default weights (25, 25, 25, 25) are used."""
    monkeypatch.setattr(
        "app.services.health_score.DATABASE_PATH", "/nonexistent/path/db.sqlite"
    )

    result = await computer.compute(0.2, 0.2, 0.2, 0.2, "Electronics")
    # Default weights (25, 25, 25, 25): 100 - (25*0.2*4) = 100 - 20 = 80
    assert result.health_score == 80
    assert result.condition == "Good"


# --- Integer rounding test ---


@pytest.mark.asyncio
async def test_score_is_integer_truncated(computer):
    """Health score is an int (truncated, not rounded)."""
    # Electronics (30, 25, 25, 20)
    # anomaly=0.1, defect=0.1, reason=0.1, wear=0.1
    # 100 - (3 + 2.5 + 2.5 + 2) = 100 - 10 = 90
    result = await computer.compute(0.1, 0.1, 0.1, 0.1, "Electronics")
    assert result.health_score == 90
    assert isinstance(result.health_score, int)
