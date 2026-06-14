"""
Property Test 10 — Below-Threshold Score Produces Null Interventions

For any risk score at or below the configured RISK_THRESHOLD, both
intervention_type and intervention_copy in the response SHALL be null.

**Validates: Requirements 5.3**
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from hypothesis import given, settings as h_settings
from hypothesis import strategies as st

from return_prevention.api.routes_risk import (
    _get_green_coin_emitter,
    router as risk_router,
)
from return_prevention.config import settings
from return_prevention.db.database import get_db


# ---------------------------------------------------------------------------
# Minimal test app setup
# ---------------------------------------------------------------------------

def _build_test_app() -> FastAPI:
    """Build a minimal FastAPI app with just the risk router."""
    app = FastAPI()
    app.include_router(risk_router)

    def override_get_db():
        mock_session = MagicMock()
        try:
            yield mock_session
        finally:
            pass

    def mock_emitter():
        emitter = MagicMock()
        emitter.emit = AsyncMock(return_value=None)
        return emitter

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[_get_green_coin_emitter] = mock_emitter
    return app


_app = _build_test_app()
_client = TestClient(_app)

# Valid payload for the risk-score endpoint
VALID_PAYLOAD: dict = {
    "customer_id": "cust_below_thresh",
    "product_id": "prod_below_thresh",
    "page_dwell_seconds": 15.0,
    "is_buy_now": False,
}


# ---------------------------------------------------------------------------
# Property Test
# ---------------------------------------------------------------------------

@given(risk_score=st.floats(0.0, 0.6, allow_nan=False, allow_infinity=False))
@h_settings(max_examples=50, deadline=10000)
def test_below_threshold_score_produces_null_interventions(risk_score: float):
    """
    Property 10: Below-Threshold Score Produces Null Interventions.

    For any generated score at or below the RISK_THRESHOLD (default 0.6),
    both intervention_type and intervention_copy must be null.

    We mock the feature assembler to return a dummy vector and the scorer
    to return our generated score, then verify the response.

    **Validates: Requirements 5.3**
    """
    import numpy as np

    # Mock the feature assembler to return a non-taxonomy-miss result
    mock_vector = np.zeros((1, 9))

    with patch(
        "return_prevention.api.routes_risk.FeatureAssembler"
    ) as MockAssembler:
        assembler_instance = MockAssembler.return_value
        assembler_instance.assemble = AsyncMock(
            return_value=(mock_vector, False)
        )

        # Mock the scorer to return our generated below-threshold score
        with patch(
            "return_prevention.api.routes_risk.risk_score_fn",
            return_value=risk_score,
        ):
            response = _client.post("/api/v1/risk-score", json=VALID_PAYLOAD)

    # The response should be 200
    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    data = response.json()

    # Assert risk_score matches
    assert data["risk_score"] == risk_score or abs(data["risk_score"] - risk_score) < 1e-9, (
        f"Expected risk_score={risk_score}, got {data['risk_score']}"
    )

    # Assert both intervention fields are null
    assert data["intervention_type"] is None, (
        f"Expected intervention_type=None for score={risk_score} "
        f"(<= threshold={settings.RISK_THRESHOLD}), "
        f"got {data['intervention_type']!r}"
    )
    assert data["intervention_copy"] is None, (
        f"Expected intervention_copy=None for score={risk_score} "
        f"(<= threshold={settings.RISK_THRESHOLD}), "
        f"got {data['intervention_copy']!r}"
    )
