"""
Tests for POST /api/returns/{return_id}/submit endpoint.

Validates: Requirements 2.7, 2.8, 3.4, 5.1, 5.2, 12.1
"""

import json
import os
import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
import aiosqlite
from httpx import ASGITransport, AsyncClient

from app.config.database import init_db
from app.main import app
from app.models.health_card import FraudSignal, HealthCard
from app.services.pipeline_orchestrator import PipelineError

TEST_DB = "test_submit_endpoint.db"


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db(monkeypatch):
    """Use a temporary test database and seed a return session."""
    monkeypatch.setattr("app.config.database.DATABASE_PATH", TEST_DB)
    monkeypatch.setattr("app.routers.returns.get_db", _get_test_db)
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    await init_db()
    # Seed a return session for testing
    async with aiosqlite.connect(TEST_DB) as db:
        await db.execute(
            """INSERT INTO returns (id, order_id, product_id, customer_id, category, delivery_date, initiated_at, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("RET-001", "ORD-123", "PROD-789", "CUST-001", "Electronics", "2026-05-01", "2026-05-15T10:00:00", "initiated"),
        )
        await db.execute(
            """INSERT INTO returns (id, order_id, product_id, customer_id, category, delivery_date, initiated_at, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("RET-002", "ORD-456", "PROD-111", "CUST-002", "Clothing & Footwear", "2026-05-01", "2026-05-10T10:00:00", "initiated"),
        )
        await db.commit()
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


async def _get_test_db():
    """Get a test database connection."""
    db = await aiosqlite.connect(TEST_DB)
    db.row_factory = aiosqlite.Row
    return db


# ---------------------------------------------------------------------------
# Valid request payloads
# ---------------------------------------------------------------------------

VALID_ELECTRONICS_QA = {
    "return_reason": "Item is defective / not working",
    "functional_status": "Not functional — does not power on / completely broken",
    "physical_condition": "Minor cosmetic damage (light scratches, small dents)",
    "accessories": "Yes — all accessories present",
    "original_packaging": "Yes — original box with all inserts",
    "ownership_duration": "Used briefly (less than a week)",
    "factory_reset": "Yes — fully reset, personal data removed",
    "liquid_damage": "No — never exposed to liquid or impact",
}

VALID_CLOTHING_QA = {
    "return_reason": "Changed my mind",
    "wear_history": "Never worn — tags still attached",
    "tag_status": "Yes — all tags attached and intact",
    "washing_history": "No — not washed",
    "staining_odour": "No — completely clean",
    "original_packaging": "Yes — original packaging intact",
    "physical_damage": "No damage",
}

VALID_CATALOG_ELECTRONICS = {
    "category": "Electronics",
    "original_price": 24999.0,
    "purchase_date": "2026-05-01",
    "warranty_remaining_months": 5,
}

VALID_CATALOG_CLOTHING = {
    "category": "Clothing & Footwear",
    "original_price": 5999.0,
    "purchase_date": "2026-05-01",
    "warranty_remaining_months": 0,
}


def _make_submit_payload(qa_answers: dict, catalog: dict, image_count: int = 3) -> dict:
    """Build a valid submit request payload."""
    return {
        "qa_answers": qa_answers,
        "image_uris": [f"s3://uploads/img{i}.jpg" for i in range(image_count)],
        "video_frame_uris": [f"s3://uploads/frame{i}.jpg" for i in range(5)],
        "catalog_metadata": catalog,
    }


def _mock_health_card() -> HealthCard:
    """Create a mock HealthCard for pipeline result."""
    return HealthCard(
        condition="Good",
        health_score=78,
        confidence=0.85,
        warranty_left_months=5,
        defects=["minor scratch"],
        anomaly_heatmap_uri="s3://heatmaps/test.png",
        justification="Good. Detected: minor scratch. No structural anomalies. Functional check: pass. Warranty: 5 months remaining.",
        disposition="refurbish",
        source="standard_return",
        fraud_signal=FraudSignal(
            social_scan_performed=False,
            product_found_in_social=False,
            fraud_confidence=0.10,
            p2p_offered=False,
            customer_chose_p2p=False,
        ),
    )


def _mock_health_card_high_fraud() -> HealthCard:
    """Create a mock HealthCard with high fraud confidence for P2P divert testing."""
    return HealthCard(
        condition="Good",
        health_score=80,
        confidence=0.90,
        warranty_left_months=0,
        defects=[],
        anomaly_heatmap_uri="s3://heatmaps/test2.png",
        justification="Good. Detected: none. No structural anomalies. Functional check: pass. Warranty: 0 months remaining.",
        disposition="resell",
        source="standard_return",
        fraud_signal=FraudSignal(
            social_scan_performed=True,
            product_found_in_social=True,
            fraud_confidence=0.75,
            p2p_offered=True,
            customer_chose_p2p=False,
        ),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_submit_return_not_found():
    """Should return 404 when return_id does not exist."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = _make_submit_payload(VALID_ELECTRONICS_QA, VALID_CATALOG_ELECTRONICS)
        response = await client.post("/api/returns/NONEXISTENT/submit", json=payload)

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_submit_invalid_qa_missing_answers():
    """Should return 400 when Q&A answers are incomplete."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        incomplete_qa = {"return_reason": "Item is defective / not working"}
        payload = _make_submit_payload(incomplete_qa, VALID_CATALOG_ELECTRONICS)
        response = await client.post("/api/returns/RET-001/submit", json=payload)

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "missing_question_ids" in detail
    assert len(detail["missing_question_ids"]) > 0


@pytest.mark.asyncio
async def test_submit_no_images():
    """Should return 400 when no image URIs are provided."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "qa_answers": VALID_ELECTRONICS_QA,
            "image_uris": [],
            "video_frame_uris": [],
            "catalog_metadata": VALID_CATALOG_ELECTRONICS,
        }
        response = await client.post("/api/returns/RET-001/submit", json=payload)

    assert response.status_code == 400
    assert "image" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_submit_too_many_images():
    """Should return 400 when more than 5 image URIs are provided."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = _make_submit_payload(VALID_ELECTRONICS_QA, VALID_CATALOG_ELECTRONICS, image_count=6)
        response = await client.post("/api/returns/RET-001/submit", json=payload)

    assert response.status_code == 400
    assert "5" in response.json()["detail"]


@pytest.mark.asyncio
@patch("app.routers.returns.PipelineOrchestrator")
async def test_submit_success_electronics(mock_orchestrator_cls):
    """Should return 200 with health card for valid Electronics submission."""
    mock_instance = AsyncMock()
    mock_instance.execute.return_value = _mock_health_card()
    mock_orchestrator_cls.return_value = mock_instance

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = _make_submit_payload(VALID_ELECTRONICS_QA, VALID_CATALOG_ELECTRONICS)
        response = await client.post("/api/returns/RET-001/submit", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert "health_card" in data
    assert data["health_card"]["condition"] == "Good"
    assert data["health_card"]["health_score"] == 78
    assert data["p2p_divert_offered"] is False


@pytest.mark.asyncio
@patch("app.routers.returns.PipelineOrchestrator")
async def test_submit_persists_health_card(mock_orchestrator_cls):
    """Should persist the health card in the health_cards table."""
    mock_instance = AsyncMock()
    mock_instance.execute.return_value = _mock_health_card()
    mock_orchestrator_cls.return_value = mock_instance

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = _make_submit_payload(VALID_ELECTRONICS_QA, VALID_CATALOG_ELECTRONICS)
        response = await client.post("/api/returns/RET-001/submit", json=payload)

    assert response.status_code == 200

    # Check that health card was persisted
    async with aiosqlite.connect(TEST_DB) as db:
        cursor = await db.execute(
            "SELECT return_id, health_card_json FROM health_cards WHERE return_id = ?",
            ("RET-001",),
        )
        row = await cursor.fetchone()

    assert row is not None
    assert row[0] == "RET-001"
    persisted = json.loads(row[1])
    assert persisted["condition"] == "Good"
    assert persisted["health_score"] == 78


@pytest.mark.asyncio
@patch("app.routers.returns.PipelineOrchestrator")
async def test_submit_updates_return_status_to_complete(mock_orchestrator_cls):
    """Should update the return status to 'complete' after successful grading."""
    mock_instance = AsyncMock()
    mock_instance.execute.return_value = _mock_health_card()
    mock_orchestrator_cls.return_value = mock_instance

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = _make_submit_payload(VALID_ELECTRONICS_QA, VALID_CATALOG_ELECTRONICS)
        response = await client.post("/api/returns/RET-001/submit", json=payload)

    assert response.status_code == 200

    # Check return status updated
    async with aiosqlite.connect(TEST_DB) as db:
        cursor = await db.execute(
            "SELECT status FROM returns WHERE id = ?", ("RET-001",)
        )
        row = await cursor.fetchone()

    assert row[0] == "complete"


@pytest.mark.asyncio
@patch("app.routers.returns.PipelineOrchestrator")
async def test_submit_pipeline_error_returns_500(mock_orchestrator_cls):
    """Should return 500 when pipeline returns PipelineError."""
    mock_instance = AsyncMock()
    mock_instance.execute.return_value = PipelineError(
        message="Grading could not be completed: all grader components failed.",
        failed_component="grader",
    )
    mock_orchestrator_cls.return_value = mock_instance

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = _make_submit_payload(VALID_ELECTRONICS_QA, VALID_CATALOG_ELECTRONICS)
        response = await client.post("/api/returns/RET-001/submit", json=payload)

    assert response.status_code == 500
    detail = response.json()["detail"]
    assert "grader" in detail["failed_component"]


@pytest.mark.asyncio
@patch("app.routers.returns.PipelineOrchestrator")
async def test_submit_p2p_divert_offered_for_clothing_high_fraud(mock_orchestrator_cls):
    """Should offer P2P divert when fraud_confidence >= 0.60 AND Clothing & Footwear."""
    mock_instance = AsyncMock()
    mock_instance.execute.return_value = _mock_health_card_high_fraud()
    mock_orchestrator_cls.return_value = mock_instance

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = _make_submit_payload(VALID_CLOTHING_QA, VALID_CATALOG_CLOTHING)
        response = await client.post("/api/returns/RET-002/submit", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["p2p_divert_offered"] is True


@pytest.mark.asyncio
@patch("app.routers.returns.PipelineOrchestrator")
async def test_submit_no_p2p_for_non_clothing_high_fraud(mock_orchestrator_cls):
    """Should NOT offer P2P divert for non-Clothing categories even with high fraud."""
    high_fraud_card = _mock_health_card_high_fraud()
    mock_instance = AsyncMock()
    mock_instance.execute.return_value = high_fraud_card
    mock_orchestrator_cls.return_value = mock_instance

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Use Electronics category (RET-001)
        payload = _make_submit_payload(VALID_ELECTRONICS_QA, VALID_CATALOG_ELECTRONICS)
        response = await client.post("/api/returns/RET-001/submit", json=payload)

    assert response.status_code == 200
    data = response.json()
    # Even if fraud_confidence is high, P2P is only for Clothing & Footwear
    assert data["p2p_divert_offered"] is False


@pytest.mark.asyncio
async def test_submit_missing_required_field():
    """Should return 422 when required fields are missing from request body."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Missing catalog_metadata
        payload = {
            "qa_answers": VALID_ELECTRONICS_QA,
            "image_uris": ["s3://img1.jpg"],
        }
        response = await client.post("/api/returns/RET-001/submit", json=payload)

    assert response.status_code == 422
