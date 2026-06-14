"""
Property Test 5 — Missing Required Field Returns 422

For any request to POST /api/v1/risk-score that is missing one or more of the
four required fields (customer_id, product_id, page_dwell_seconds, is_buy_now),
the service SHALL return HTTP 422 and SHALL NOT compute a risk score.

**Validates: Requirements 1.8**
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st

from return_prevention.api.routes_risk import (
    _get_green_coin_emitter,
    router as risk_router,
)
from return_prevention.db.database import get_db


# ---------------------------------------------------------------------------
# Minimal test app setup (no model loading needed — request rejected before scoring)
# ---------------------------------------------------------------------------

def _build_test_app() -> FastAPI:
    """Build a minimal FastAPI app with just the risk router for testing."""
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

# A valid payload containing all required fields
VALID_PAYLOAD: dict = {
    "customer_id": "cust_prop_test",
    "product_id": "prod_prop_test",
    "page_dwell_seconds": 15.0,
    "is_buy_now": False,
}


# ---------------------------------------------------------------------------
# Property 5: Missing Required Field Returns 422
# ---------------------------------------------------------------------------

@given(field_to_drop=st.sampled_from(["customer_id", "product_id", "page_dwell_seconds", "is_buy_now"]))
@settings(max_examples=50)
def test_missing_required_field_returns_422(field_to_drop: str) -> None:
    """
    Property 5: Missing Required Field Returns 422

    For any one of the four required fields dropped from the request,
    the endpoint returns HTTP 422 and no score computation occurs.

    **Validates: Requirements 1.8**
    """
    payload = VALID_PAYLOAD.copy()
    del payload[field_to_drop]

    # Patch the scorer to detect if scoring was attempted
    with patch(
        "return_prevention.core.scorer.score",
        side_effect=AssertionError("Score computation should not be reached"),
    ) as mock_score:
        response = _client.post("/api/v1/risk-score", json=payload)

    # Assert HTTP 422
    assert response.status_code == 422, (
        f"Expected 422 when '{field_to_drop}' is missing, got {response.status_code}"
    )

    # Assert no score computation occurred
    mock_score.assert_not_called()
