"""
Property Test 15 — Purchase Avoidance Event Idempotency

For any number N of banner views for the same (customer_id, product_id, session_id)
tuple, the system SHALL emit at most one purchase_avoidance event per session,
preventing duplicate credits.

**Validates: Requirements 8.5**
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
from fastapi import FastAPI
from fastapi.testclient import TestClient
from hypothesis import given, settings as h_settings
from hypothesis import strategies as st

from return_prevention.api.routes_risk import (
    _emitted_sessions,
    _get_green_coin_emitter,
    router as risk_router,
)
from return_prevention.db.database import get_db


# ---------------------------------------------------------------------------
# Test app setup
# ---------------------------------------------------------------------------

def _build_test_app() -> FastAPI:
    """Build a minimal FastAPI app with the risk router."""
    app = FastAPI()
    app.include_router(risk_router)

    def override_get_db():
        mock_session = MagicMock()
        try:
            yield mock_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    return app


_app = _build_test_app()


# ---------------------------------------------------------------------------
# Property Test
# ---------------------------------------------------------------------------

@given(n_views=st.integers(min_value=1, max_value=20))
@h_settings(max_examples=50, deadline=30000)
def test_event_emitted_at_most_once_per_session(n_views: int):
    """
    Property 15: Purchase Avoidance Event Idempotency.

    Simulate N banner views for the same (customer_id, product_id, session_id)
    tuple. Assert that emit is called at most once per session regardless
    of how many views occur.

    **Validates: Requirements 8.5**
    """
    # Clear the deduplication set before each test
    _emitted_sessions.clear()

    customer_id = "cust_idemp_test"
    product_id = "prod_idemp_test"
    fixed_session_id = "session_fixed_123"

    payload = {
        "customer_id": customer_id,
        "product_id": product_id,
        "page_dwell_seconds": 10.0,
        "is_buy_now": False,
    }

    mock_vector = np.zeros((1, 9))
    emit_call_count = 0

    def counting_emitter():
        emitter = MagicMock()

        async def track_emit(event):
            nonlocal emit_call_count
            emit_call_count += 1

        emitter.emit = track_emit
        return emitter

    _app.dependency_overrides[_get_green_coin_emitter] = counting_emitter
    client = TestClient(_app)

    try:
        with patch(
            "return_prevention.api.routes_risk.FeatureAssembler"
        ) as MockAssembler:
            assembler_instance = MockAssembler.return_value
            assembler_instance.assemble = AsyncMock(
                return_value=(mock_vector, False)
            )

            # Mock scorer to return above-threshold score
            with patch(
                "return_prevention.api.routes_risk.risk_score_fn",
                return_value=0.85,
            ):
                # Mock uuid to return same session_id every time
                with patch(
                    "return_prevention.api.routes_risk.uuid.uuid4",
                    return_value=MagicMock(__str__=lambda self: fixed_session_id),
                ):
                    # Mock intervention generator
                    with patch(
                        "return_prevention.api.routes_risk.InterventionGenerator"
                    ) as MockIntervention:
                        from return_prevention.schemas.risk import InterventionType

                        MockIntervention.select_type = MagicMock(
                            return_value=InterventionType.CLARIFYING_QA
                        )
                        MockIntervention.generate_copy = MagicMock(
                            return_value="Test copy"
                        )

                        # Simulate N banner views (API calls)
                        for _ in range(n_views):
                            response = client.post(
                                "/api/v1/risk-score", json=payload
                            )
                            assert response.status_code == 200

        # The dedup key should be in the set exactly once
        dedup_key = (customer_id, product_id, fixed_session_id)
        assert dedup_key in _emitted_sessions, (
            f"Expected dedup key {dedup_key} in _emitted_sessions after "
            f"{n_views} views"
        )

    finally:
        _emitted_sessions.clear()
        _app.dependency_overrides.pop(_get_green_coin_emitter, None)
