"""
Property Test 16 — Customer_Profile Fallback Produces Valid Score

When the CustomerProfileClient raises a timeout exception on every call,
the system SHALL still respond with HTTP 200 and a valid risk_score in [0.0, 1.0].

**Validates: Requirements 9.2**
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from hypothesis import given, settings as h_settings, HealthCheck
from hypothesis import strategies as st

from return_prevention.api.routes_risk import (
    _emitted_sessions,
    _get_green_coin_emitter,
    router as risk_router,
)
from return_prevention.core.model_registry import ModelRegistry
from return_prevention.db.database import get_db
from return_prevention.taxonomy.taxonomy_loader import TaxonomyEntry

# Path to the real pre-trained model
MODEL_PATH = str(
    Path(__file__).resolve().parent.parent.parent / "ml" / "models" / "lgbm_return_risk.pkl"
)

# A known taxonomy fixture for the test product_id
_TEST_TAXONOMY = {
    "test_product": TaxonomyEntry(
        category="Electronics",
        subcategory="test_product",
        category_return_rate=0.15,
        has_size_ambiguity=False,
    )
}


# ---------------------------------------------------------------------------
# Strategy for valid RiskScoreRequest payloads
# ---------------------------------------------------------------------------

def score_request_strategy():
    """Generate valid RiskScoreRequest payloads with a fixed product_id in taxonomy."""
    return st.fixed_dictionaries({
        "customer_id": st.text(min_size=1, max_size=20, alphabet=st.characters(
            whitelist_categories=("Lu", "Ll", "Nd"),
        )),
        "product_id": st.just("test_product"),  # Must be in taxonomy
        "page_dwell_seconds": st.floats(
            min_value=0.0, max_value=300.0,
            allow_nan=False, allow_infinity=False,
        ),
        "is_buy_now": st.booleans(),
        "seller_id": st.just("seller_001"),
        "product_price": st.floats(
            min_value=10.0, max_value=5000.0,
            allow_nan=False, allow_infinity=False,
        ),
        "is_sale_active": st.booleans(),
    })


# ---------------------------------------------------------------------------
# Test app setup
# ---------------------------------------------------------------------------

def _build_test_app() -> FastAPI:
    """Build a minimal FastAPI app with the risk router and real model."""
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


# Load the real model once
def _ensure_model_loaded():
    """Load the real LightGBM model for scoring."""
    ModelRegistry._instance = None
    registry = ModelRegistry()
    registry.load(MODEL_PATH)
    return registry


_app = _build_test_app()
_client = TestClient(_app)


# ---------------------------------------------------------------------------
# Property Test
# ---------------------------------------------------------------------------

@given(payload=score_request_strategy())
@h_settings(
    max_examples=50,
    deadline=30000,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_customer_profile_fallback_produces_valid_score(payload: dict):
    """
    Property 16: Customer_Profile Fallback Produces Valid Score.

    When CustomerProfileClient raises httpx.TimeoutException on every call,
    the service should still respond with HTTP 200 and a risk_score in [0.0, 1.0].

    **Validates: Requirements 9.2**
    """
    # Clear dedup set to avoid interference between runs
    _emitted_sessions.clear()

    # Ensure model is loaded
    _ensure_model_loaded()

    # Mock the taxonomy to return our known fixture
    with patch(
        "return_prevention.core.feature_assembler.get_taxonomy",
        return_value=_TEST_TAXONOMY,
    ):
        # Mock CustomerProfileClient.get to always raise TimeoutException
        with patch(
            "return_prevention.core.feature_assembler.CustomerProfileClient"
        ) as MockClientCls:
            mock_client_instance = MockClientCls.return_value
            mock_client_instance.get = AsyncMock(
                side_effect=httpx.TimeoutException("Connection timed out")
            )

            # Mock seller profile to return a known value
            with patch(
                "return_prevention.core.feature_assembler.SellerProfileRepository"
            ) as MockSellerRepo:
                MockSellerRepo.get.return_value = None
                MockSellerRepo.get_global_mean.return_value = 0.12

                # Mock price band profile
                with patch(
                    "return_prevention.core.feature_assembler.PriceBandProfileRepository"
                ) as MockPriceBandRepo:
                    MockPriceBandRepo.get_high_return_band.return_value = None

                    # Mock the intervention generator and taxonomy for the route
                    with patch(
                        "return_prevention.api.routes_risk.get_taxonomy",
                        return_value=_TEST_TAXONOMY,
                    ):
                        with patch(
                            "return_prevention.api.routes_risk.FitProfileRepository"
                        ) as MockFitRepo:
                            MockFitRepo.count.return_value = 0

                            response = _client.post(
                                "/api/v1/risk-score", json=payload
                            )

    # Assert HTTP 200
    assert response.status_code == 200, (
        f"Expected HTTP 200, got {response.status_code}: {response.text}"
    )

    data = response.json()

    # Assert risk_score is present and in [0.0, 1.0]
    assert "risk_score" in data, f"Response missing 'risk_score': {data}"
    risk_score = data["risk_score"]
    assert isinstance(risk_score, (int, float)), (
        f"risk_score is not a number: {type(risk_score)}"
    )
    assert 0.0 <= risk_score <= 1.0, (
        f"risk_score {risk_score} is outside valid range [0.0, 1.0] "
        f"when CustomerProfileClient times out"
    )
