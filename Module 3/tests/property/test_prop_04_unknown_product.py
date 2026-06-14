"""
Property Test 4 — Unknown Product Short-Circuit

For any product_id whose subcategory has no match in the Category_Taxonomy,
the /api/v1/risk-score response SHALL have risk_score == 0.0,
intervention_type == null, and intervention_copy == null.

**Validates: Requirements 1.6, 3.8**
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from hypothesis import given, settings as hyp_settings
from hypothesis import strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from return_prevention.api.routes_risk import (
    _get_green_coin_emitter,
    router as risk_router,
)
from return_prevention.core.model_registry import ModelRegistry
from return_prevention.db.database import Base, get_db
from return_prevention.db.repositories import seed_global_seller
from return_prevention.taxonomy.taxonomy_loader import TaxonomyEntry


# ---------------------------------------------------------------------------
# Taxonomy fixture — defines the known subcategories
# ---------------------------------------------------------------------------

TAXONOMY_FIXTURE: dict[str, TaxonomyEntry] = {
    "Women's Shoes": TaxonomyEntry(
        category="Apparel",
        subcategory="Women's Shoes",
        category_return_rate=0.35,
        has_size_ambiguity=True,
    ),
    "Men's Jeans": TaxonomyEntry(
        category="Apparel",
        subcategory="Men's Jeans",
        category_return_rate=0.28,
        has_size_ambiguity=True,
    ),
    "Smartphones": TaxonomyEntry(
        category="Electronics",
        subcategory="Smartphones",
        category_return_rate=0.08,
        has_size_ambiguity=False,
    ),
    "Earphones": TaxonomyEntry(
        category="Electronics",
        subcategory="Earphones",
        category_return_rate=0.12,
        has_size_ambiguity=False,
    ),
    "Blenders": TaxonomyEntry(
        category="Home",
        subcategory="Blenders",
        category_return_rate=0.05,
        has_size_ambiguity=False,
    ),
}

KNOWN_SUBCATEGORIES = set(TAXONOMY_FIXTURE.keys())


# ---------------------------------------------------------------------------
# Test infrastructure setup
# ---------------------------------------------------------------------------


def _create_test_app():
    """Build a FastAPI app with an in-memory SQLite DB and seeded global seller."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Seed the global seller
    session = TestSession()
    seed_global_seller(session)
    session.close()

    app = FastAPI()
    app.include_router(risk_router)

    def override_get_db():
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    def _mock_green_coin_emitter():
        mock = MagicMock()
        mock.emit = AsyncMock(return_value=None)
        return mock

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[_get_green_coin_emitter] = _mock_green_coin_emitter
    return app


# Load the real model once for the module
_registry = ModelRegistry()
_registry.load("ml/models/lgbm_return_risk.pkl")

# Create the app and client once
_app = _create_test_app()
_client = TestClient(_app)


# ---------------------------------------------------------------------------
# Property 4: Unknown Product Short-Circuit
# ---------------------------------------------------------------------------


@hyp_settings(max_examples=50, deadline=5000)
@given(
    product_id=st.text(min_size=1).filter(lambda s: s not in KNOWN_SUBCATEGORIES)
)
def test_unknown_product_short_circuits(product_id: str):
    """
    Property 4: Unknown Product Short-Circuit

    For any product_id not present in the Category_Taxonomy keys, the API
    must return risk_score == 0.0, intervention_type is None,
    intervention_copy is None, and taxonomy_miss is True.

    **Validates: Requirements 1.6, 3.8**
    """
    payload = {
        "customer_id": "test_customer",
        "product_id": product_id,
        "page_dwell_seconds": 5.0,
        "is_buy_now": False,
        "seller_id": None,
        "product_price": 1000.0,
        "is_sale_active": False,
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
        response = _client.post("/api/v1/risk-score", json=payload)

    assert response.status_code == 200, (
        f"Expected 200 but got {response.status_code} for product_id={product_id!r}"
    )

    data = response.json()
    assert data["risk_score"] == 0.0, (
        f"Expected risk_score == 0.0 but got {data['risk_score']} "
        f"for unknown product_id={product_id!r}"
    )
    assert data["intervention_type"] is None, (
        f"Expected intervention_type to be None but got {data['intervention_type']} "
        f"for unknown product_id={product_id!r}"
    )
    assert data["intervention_copy"] is None, (
        f"Expected intervention_copy to be None but got {data['intervention_copy']} "
        f"for unknown product_id={product_id!r}"
    )
    assert data["taxonomy_miss"] is True, (
        f"Expected taxonomy_miss to be True but got {data['taxonomy_miss']} "
        f"for unknown product_id={product_id!r}"
    )
