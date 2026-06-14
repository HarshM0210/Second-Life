"""
Unit and integration tests for API routes:
- POST /api/v1/risk-score
- GET  /api/v1/fit-profile/{customer_id}
- POST /api/v1/model/reload
- GET  /api/v1/model/feature-importance

Requirements: 1.7, 1.8, 1.9, 2.9, 2.10, 4.5, 4.7
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from return_prevention.api.routes_fit import router as fit_router
from return_prevention.api.routes_model import router as model_router
from return_prevention.api.routes_risk import (
    _get_green_coin_emitter,
    router as risk_router,
)
from return_prevention.core.model_registry import ModelRegistry
from return_prevention.db.database import Base, get_db
from return_prevention.db.models import FitProfileRow, SellerProfileRow
from return_prevention.db.repositories import seed_global_seller
from return_prevention.taxonomy.taxonomy_loader import TaxonomyEntry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TAXONOMY_FIXTURE: dict[str, TaxonomyEntry] = {
    "Women's Shoes": TaxonomyEntry(
        category="Apparel",
        subcategory="Women's Shoes",
        category_return_rate=0.35,
        has_size_ambiguity=True,
    ),
    "Smartphones": TaxonomyEntry(
        category="Electronics",
        subcategory="Smartphones",
        category_return_rate=0.08,
        has_size_ambiguity=False,
    ),
}


def _mock_green_coin_emitter():
    """Return a mock GreenCoinEmitter that doesn't make real HTTP calls."""
    mock = MagicMock()
    mock.emit = AsyncMock(return_value=None)
    return mock


@pytest.fixture(autouse=True)
def reset_model_registry():
    """Reset ModelRegistry singleton before each test."""
    ModelRegistry._instance = None
    yield
    ModelRegistry._instance = None


@pytest.fixture()
def test_engine(tmp_path):
    """Create a file-based SQLite engine with all tables."""
    db_path = tmp_path / "test.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture()
def session_factory(test_engine):
    """Return a sessionmaker bound to the test engine."""
    return sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture()
def db_session(session_factory):
    """Yield a fresh database session."""
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def app(session_factory):
    """Build a FastAPI app with all routers and override get_db."""
    application = FastAPI()
    application.include_router(risk_router)
    application.include_router(fit_router)
    application.include_router(model_router)

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    application.dependency_overrides[get_db] = override_get_db
    application.dependency_overrides[_get_green_coin_emitter] = _mock_green_coin_emitter
    return application


@pytest.fixture()
def client(app):
    """Return a TestClient for the app."""
    return TestClient(app)


@pytest.fixture()
def seeded_app(session_factory):
    """
    Build a FastAPI app with all routers, seed the global seller,
    and set up for the risk-score integration test.
    """
    application = FastAPI()
    application.include_router(risk_router)
    application.include_router(fit_router)
    application.include_router(model_router)

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    application.dependency_overrides[get_db] = override_get_db
    application.dependency_overrides[_get_green_coin_emitter] = _mock_green_coin_emitter

    # Seed global seller in the DB
    session = session_factory()
    seed_global_seller(session)
    session.close()

    return application


@pytest.fixture()
def seeded_client(seeded_app):
    """Return a TestClient for the seeded app."""
    return TestClient(seeded_app)


# ---------------------------------------------------------------------------
# POST /api/v1/risk-score — HTTP 200 integration test
# ---------------------------------------------------------------------------


class TestRiskScoreSuccess:
    """POST /api/v1/risk-score with valid input → HTTP 200 with correct shape."""

    def test_risk_score_200_response_shape(self, seeded_client):
        """
        With all required fields, real SQLite DB, taxonomy fixture, and loaded model,
        the endpoint should return HTTP 200 with correct response keys.
        Validates: Requirements 1.7
        """
        # Load the real model
        registry = ModelRegistry()
        registry.load("ml/models/lgbm_return_risk.pkl")

        payload = {
            "customer_id": "cust_integration_test",
            "product_id": "Women's Shoes",
            "page_dwell_seconds": 12.5,
            "is_buy_now": False,
            "seller_id": None,
            "product_price": 1500.0,
            "is_sale_active": False,
        }

        # Mock taxonomy and customer profile to avoid real HTTP calls
        with patch(
            "return_prevention.api.routes_risk.get_taxonomy",
            return_value=TAXONOMY_FIXTURE,
        ), patch(
            "return_prevention.core.feature_assembler.get_taxonomy",
            return_value=TAXONOMY_FIXTURE,
        ), patch(
            "return_prevention.core.feature_assembler.CustomerProfileClient",
        ) as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.get = AsyncMock(return_value=None)
            response = seeded_client.post("/api/v1/risk-score", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "risk_score" in data
        assert "intervention_type" in data
        assert "intervention_copy" in data
        assert "taxonomy_miss" in data
        assert isinstance(data["risk_score"], float)
        assert 0.0 <= data["risk_score"] <= 1.0
        assert data["taxonomy_miss"] is False


# ---------------------------------------------------------------------------
# POST /api/v1/risk-score — HTTP 422 missing required fields
# ---------------------------------------------------------------------------


class TestRiskScore422:
    """POST /api/v1/risk-score missing required fields → HTTP 422."""

    VALID_PAYLOAD = {
        "customer_id": "cust_001",
        "product_id": "Women's Shoes",
        "page_dwell_seconds": 10.0,
        "is_buy_now": True,
    }

    @pytest.mark.parametrize(
        "missing_field",
        ["customer_id", "product_id", "page_dwell_seconds", "is_buy_now"],
    )
    def test_missing_required_field_returns_422(self, client, missing_field):
        """
        Removing one required field at a time should return HTTP 422.
        Validates: Requirements 1.8
        """
        payload = self.VALID_PAYLOAD.copy()
        del payload[missing_field]

        response = client.post("/api/v1/risk-score", json=payload)
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/v1/risk-score — HTTP 503 on DB failure
# ---------------------------------------------------------------------------


class TestRiskScore503:
    """POST /api/v1/risk-score with DB session mocked to raise → HTTP 503."""

    def test_db_failure_returns_503(self):
        """
        When the DB session raises an exception during use, the endpoint returns 503.
        Validates: Requirements 1.9
        """
        application = FastAPI()
        application.include_router(risk_router)

        def broken_get_db():
            """Yield a mock session that raises on any query."""
            mock_session = MagicMock(spec=Session)
            mock_session.query.side_effect = RuntimeError("Database connection failed")
            try:
                yield mock_session
            finally:
                pass

        application.dependency_overrides[get_db] = broken_get_db
        application.dependency_overrides[_get_green_coin_emitter] = _mock_green_coin_emitter

        # Load the model so model-loading isn't the error
        registry = ModelRegistry()
        registry.load("ml/models/lgbm_return_risk.pkl")

        test_client = TestClient(application)
        payload = {
            "customer_id": "cust_001",
            "product_id": "Women's Shoes",
            "page_dwell_seconds": 10.0,
            "is_buy_now": True,
        }

        with patch(
            "return_prevention.api.routes_risk.get_taxonomy",
            return_value=TAXONOMY_FIXTURE,
        ), patch(
            "return_prevention.core.feature_assembler.get_taxonomy",
            return_value=TAXONOMY_FIXTURE,
        ), patch(
            "return_prevention.core.feature_assembler.CustomerProfileClient",
        ) as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.get = AsyncMock(return_value=None)
            response = test_client.post("/api/v1/risk-score", json=payload)

        assert response.status_code == 503
        data = response.json()
        assert "detail" in data


# ---------------------------------------------------------------------------
# GET /api/v1/fit-profile/{customer_id} — empty → HTTP 200 with {}
# ---------------------------------------------------------------------------


class TestFitProfileEmpty:
    """GET /api/v1/fit-profile with no rows → HTTP 200 with {}."""

    def test_no_rows_returns_empty_dict(self, client):
        """
        When no FitProfile rows exist for the customer, returns HTTP 200 with {}.
        Validates: Requirements 2.9, 2.10
        """
        response = client.get("/api/v1/fit-profile/nonexistent_customer")
        assert response.status_code == 200
        assert response.json() == {}


# ---------------------------------------------------------------------------
# GET /api/v1/fit-profile/{customer_id} — seeded rows → correct grouping
# ---------------------------------------------------------------------------


class TestFitProfileGroupedByBrand:
    """GET /api/v1/fit-profile with seeded rows → correct grouping by brand."""

    def test_seeded_rows_grouped_by_brand(self, session_factory):
        """
        When FitProfile rows exist for different brands, they are grouped correctly.
        Validates: Requirements 2.9
        """
        # Seed rows
        session = session_factory()
        session.add(FitProfileRow(
            customer_id="cust_fit_01",
            brand="Nike",
            order_id="ORD-FIT-001",
            purchased_size="UK 9",
            status="kept",
            return_reason=None,
        ))
        session.add(FitProfileRow(
            customer_id="cust_fit_01",
            brand="Nike",
            order_id="ORD-FIT-002",
            purchased_size="UK 10",
            status="returned",
            return_reason="too large",
        ))
        session.add(FitProfileRow(
            customer_id="cust_fit_01",
            brand="Levi's",
            order_id="ORD-FIT-003",
            purchased_size="32",
            status="pending",
            return_reason=None,
        ))
        session.commit()
        session.close()

        # Build app with this DB
        application = FastAPI()
        application.include_router(fit_router)

        def override_get_db():
            s = session_factory()
            try:
                yield s
            finally:
                s.close()

        application.dependency_overrides[get_db] = override_get_db
        test_client = TestClient(application)

        response = test_client.get("/api/v1/fit-profile/cust_fit_01")
        assert response.status_code == 200
        data = response.json()

        # Check grouped by brand
        assert "Nike" in data
        assert "Levi's" in data
        assert len(data["Nike"]) == 2
        assert len(data["Levi's"]) == 1

        # Verify entry content
        nike_orders = data["Nike"]
        order_ids = [entry["order_id"] for entry in nike_orders]
        assert "ORD-FIT-001" in order_ids
        assert "ORD-FIT-002" in order_ids

        levis_entry = data["Levi's"][0]
        assert levis_entry["order_id"] == "ORD-FIT-003"
        assert levis_entry["purchased_size"] == "32"
        assert levis_entry["status"] == "pending"
        assert levis_entry["return_reason"] is None


# ---------------------------------------------------------------------------
# POST /api/v1/model/reload → HTTP 200 with file_mtime
# ---------------------------------------------------------------------------


class TestModelReload:
    """POST /api/v1/model/reload → HTTP 200 with updated file_mtime."""

    def test_reload_returns_200_with_mtime(self, client):
        """
        Reload endpoint from allowed host returns 200 with file_mtime.
        TestClient reports client.host as 'testclient', so we patch INTERNAL_HOSTS.
        Validates: Requirements 4.5
        """
        # Load the model first so reload has something to swap
        registry = ModelRegistry()
        registry.load("ml/models/lgbm_return_risk.pkl")

        with patch(
            "return_prevention.api.routes_model.INTERNAL_HOSTS",
            ["127.0.0.1", "localhost", "testclient"],
        ):
            response = client.post("/api/v1/model/reload")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "reloaded"
        assert "file_mtime" in data
        assert "model_path" in data
        # file_mtime should be a valid ISO datetime string
        assert "T" in data["file_mtime"]


# ---------------------------------------------------------------------------
# GET /api/v1/model/feature-importance → exactly 9 keys, all non-negative
# ---------------------------------------------------------------------------


class TestFeatureImportance:
    """GET /api/v1/model/feature-importance → exactly 9 keys, all non-negative."""

    def test_feature_importance_has_9_keys(self, client):
        """
        The feature-importance endpoint returns exactly 9 keys with
        non-negative values.
        Validates: Requirements 4.7
        """
        # Load the model
        registry = ModelRegistry()
        registry.load("ml/models/lgbm_return_risk.pkl")

        response = client.get("/api/v1/model/feature-importance")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 9

        # All values should be non-negative
        for key, value in data.items():
            assert value >= 0, f"Feature {key} has negative importance: {value}"

        # Verify expected feature names are present
        from return_prevention.core.model_registry import FEATURE_COLS

        for col in FEATURE_COLS:
            assert col in data, f"Missing feature: {col}"
