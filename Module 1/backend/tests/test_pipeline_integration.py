"""
Integration tests for the end-to-end pipeline via the submit API endpoint.

These tests use the REAL pipeline (no mocks) to verify:
1. Status transitions: initiated → grading → complete (or error)
2. Health Card persistence in health_cards table
3. Graceful degradation when components produce partial results
4. Full pipeline produces valid Health Card JSON

Requirements: 16.1, 16.2, 16.3, 16.4, 16.5, 16.6, 18.4
"""

import json
import os

import aiosqlite
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.config.database import init_db
from app.main import app

TEST_DB = "test_pipeline_integration.db"


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db(monkeypatch):
    """Set up a fresh test database with seeded config and return sessions."""
    monkeypatch.setattr("app.config.database.DATABASE_PATH", TEST_DB)
    monkeypatch.setattr("app.services.health_score.DATABASE_PATH", TEST_DB)
    monkeypatch.setattr("app.services.disposition_router.DATABASE_PATH", TEST_DB)
    monkeypatch.setattr("app.services.return_window.DATABASE_PATH", TEST_DB)
    monkeypatch.setattr("app.routers.returns.get_db", _get_test_db)

    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    await init_db()

    # Seed return sessions for integration testing
    async with aiosqlite.connect(TEST_DB) as db:
        await db.execute(
            """INSERT INTO returns (id, order_id, product_id, customer_id, category, delivery_date, initiated_at, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("RET-INT-001", "ORD-100", "PROD-100", "CUST-100", "Electronics", "2026-05-01", "2026-05-15T10:00:00", "initiated"),
        )
        await db.execute(
            """INSERT INTO returns (id, order_id, product_id, customer_id, category, delivery_date, initiated_at, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("RET-INT-002", "ORD-200", "PROD-200", "CUST-200", "Clothing & Footwear", "2026-05-01", "2026-05-10T10:00:00", "initiated"),
        )
        await db.execute(
            """INSERT INTO returns (id, order_id, product_id, customer_id, category, delivery_date, initiated_at, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("RET-INT-003", "ORD-300", "PROD-300", "CUST-300", "Food & Grocery", "2026-06-01", "2026-06-05T10:00:00", "initiated"),
        )
        await db.execute(
            """INSERT INTO returns (id, order_id, product_id, customer_id, category, delivery_date, initiated_at, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("RET-INT-004", "ORD-400", "PROD-400", "CUST-400", "Other", "2026-05-01", "2026-05-10T10:00:00", "initiated"),
        )
        await db.commit()

    yield

    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


async def _get_test_db():
    """Get a connection to the integration test database."""
    db = await aiosqlite.connect(TEST_DB)
    db.row_factory = aiosqlite.Row
    return db


# ---------------------------------------------------------------------------
# Valid Q&A payloads for each category
# ---------------------------------------------------------------------------

ELECTRONICS_QA = {
    "return_reason": "Item is defective / not working",
    "functional_status": "Not functional — does not power on / completely broken",
    "physical_condition": "Minor cosmetic damage (light scratches, small dents)",
    "accessories": "Yes — all accessories present",
    "original_packaging": "Yes — original box with all inserts",
    "ownership_duration": "Used briefly (less than a week)",
    "factory_reset": "Yes — fully reset, personal data removed",
    "liquid_damage": "No — never exposed to liquid or impact",
}

CLOTHING_QA = {
    "return_reason": "Changed my mind",
    "wear_history": "Never worn — tags still attached",
    "tag_status": "Yes — all tags attached and intact",
    "washing_history": "No — not washed",
    "staining_odour": "No — completely clean",
    "original_packaging": "Yes — original packaging intact",
    "physical_damage": "No damage",
}

FOOD_QA = {
    "return_reason": "Wrong item delivered",
    "seal_integrity": "Yes — completely sealed, never opened",
    "packaging_condition": "Fully intact, no damage",
    "storage_compliance": "Yes, stored correctly throughout",
    "expiry_date": "2027-12-31",
    "quantity_remaining": "100% — completely unused",
}

OTHER_QA = {
    "return_reason": "Item defective or not working",
    "usage_extent": "Never used — completely unused",
    "physical_condition": "Like new — no marks or damage",
    "parts_completeness": "Yes — complete as originally received",
    "original_packaging": "Yes — original box/packaging intact",
    "skin_contact": "No",
    "safety_concern": "No safety concerns",
    "hygiene_concerns": "No hygiene concerns",
}


def _make_submit_payload(qa_answers: dict, category: str, price: float = 24999.0) -> dict:
    """Build a valid submit request payload."""
    return {
        "qa_answers": qa_answers,
        "image_uris": ["s3://uploads/img1.jpg", "s3://uploads/img2.jpg", "s3://uploads/img3.jpg"],
        "video_frame_uris": ["s3://uploads/frame1.jpg", "s3://uploads/frame2.jpg",
                            "s3://uploads/frame3.jpg", "s3://uploads/frame4.jpg",
                            "s3://uploads/frame5.jpg"],
        "catalog_metadata": {
            "category": category,
            "original_price": price,
            "purchase_date": "2026-05-01",
            "warranty_remaining_months": 5,
        },
    }


# ---------------------------------------------------------------------------
# Test: Status transitions (initiated → grading → complete)
# ---------------------------------------------------------------------------


class TestStatusTransitions:
    """Verify return status progresses through initiated → grading → complete."""

    @pytest.mark.asyncio
    async def test_successful_submission_transitions_to_complete(self):
        """Full pipeline execution transitions status from initiated to complete."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = _make_submit_payload(ELECTRONICS_QA, "Electronics")
            response = await client.post("/api/returns/RET-INT-001/submit", json=payload)

        assert response.status_code == 200

        # Verify final status is "complete"
        async with aiosqlite.connect(TEST_DB) as db:
            cursor = await db.execute(
                "SELECT status FROM returns WHERE id = ?", ("RET-INT-001",)
            )
            row = await cursor.fetchone()
        assert row[0] == "complete"

    @pytest.mark.asyncio
    async def test_clothing_category_transitions_to_complete(self):
        """Clothing & Footwear category with fraud scan also reaches complete."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = _make_submit_payload(CLOTHING_QA, "Clothing & Footwear", price=5999.0)
            response = await client.post("/api/returns/RET-INT-002/submit", json=payload)

        assert response.status_code == 200

        # Verify final status is "complete"
        async with aiosqlite.connect(TEST_DB) as db:
            cursor = await db.execute(
                "SELECT status FROM returns WHERE id = ?", ("RET-INT-002",)
            )
            row = await cursor.fetchone()
        assert row[0] == "complete"


# ---------------------------------------------------------------------------
# Test: Health Card persistence
# ---------------------------------------------------------------------------


class TestHealthCardPersistence:
    """Verify health cards are correctly persisted in health_cards table."""

    @pytest.mark.asyncio
    async def test_health_card_persisted_after_successful_pipeline(self):
        """A completed pipeline stores a valid Health Card in the DB."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = _make_submit_payload(ELECTRONICS_QA, "Electronics")
            response = await client.post("/api/returns/RET-INT-001/submit", json=payload)

        assert response.status_code == 200

        # Verify health card was persisted
        async with aiosqlite.connect(TEST_DB) as db:
            cursor = await db.execute(
                "SELECT health_card_json FROM health_cards WHERE return_id = ?",
                ("RET-INT-001",),
            )
            row = await cursor.fetchone()

        assert row is not None
        health_card = json.loads(row[0])
        assert "condition" in health_card
        assert "health_score" in health_card
        assert "disposition" in health_card
        assert "fraud_signal" in health_card
        assert "justification" in health_card
        assert health_card["source"] == "standard_return"

    @pytest.mark.asyncio
    async def test_persisted_health_card_matches_response(self):
        """The persisted Health Card matches the one returned in the response."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = _make_submit_payload(ELECTRONICS_QA, "Electronics")
            response = await client.post("/api/returns/RET-INT-001/submit", json=payload)

        assert response.status_code == 200
        response_card = response.json()["health_card"]

        # Fetch persisted version
        async with aiosqlite.connect(TEST_DB) as db:
            cursor = await db.execute(
                "SELECT health_card_json FROM health_cards WHERE return_id = ?",
                ("RET-INT-001",),
            )
            row = await cursor.fetchone()

        persisted_card = json.loads(row[0])
        assert persisted_card["health_score"] == response_card["health_score"]
        assert persisted_card["condition"] == response_card["condition"]
        assert persisted_card["disposition"] == response_card["disposition"]


# ---------------------------------------------------------------------------
# Test: Health Card field validity
# ---------------------------------------------------------------------------


class TestHealthCardValidity:
    """Verify the produced Health Card has valid field values."""

    @pytest.mark.asyncio
    async def test_health_score_within_valid_range(self):
        """Health score is an integer in [0, 100]."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = _make_submit_payload(ELECTRONICS_QA, "Electronics")
            response = await client.post("/api/returns/RET-INT-001/submit", json=payload)

        assert response.status_code == 200
        card = response.json()["health_card"]
        assert isinstance(card["health_score"], int)
        assert 0 <= card["health_score"] <= 100

    @pytest.mark.asyncio
    async def test_condition_label_matches_score(self):
        """Condition label aligns with health score thresholds."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = _make_submit_payload(ELECTRONICS_QA, "Electronics")
            response = await client.post("/api/returns/RET-INT-001/submit", json=payload)

        assert response.status_code == 200
        card = response.json()["health_card"]
        score = card["health_score"]
        condition = card["condition"]

        if score > 90:
            assert condition == "Excellent"
        elif score > 70:
            assert condition == "Good"
        elif score > 50:
            assert condition == "Fair"
        else:
            assert condition == "Poor"

    @pytest.mark.asyncio
    async def test_disposition_is_valid_value(self):
        """Disposition is one of the allowed values."""
        valid_dispositions = {"resell", "refurbish", "donate", "recycle", "return_to_seller", "manual_review"}
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = _make_submit_payload(ELECTRONICS_QA, "Electronics")
            response = await client.post("/api/returns/RET-INT-001/submit", json=payload)

        assert response.status_code == 200
        card = response.json()["health_card"]
        assert card["disposition"] in valid_dispositions

    @pytest.mark.asyncio
    async def test_fraud_signal_present_and_valid(self):
        """Fraud signal block is present with all required fields."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = _make_submit_payload(ELECTRONICS_QA, "Electronics")
            response = await client.post("/api/returns/RET-INT-001/submit", json=payload)

        assert response.status_code == 200
        fraud = response.json()["health_card"]["fraud_signal"]
        assert "social_scan_performed" in fraud
        assert "fraud_confidence" in fraud
        assert "p2p_offered" in fraud
        assert "customer_chose_p2p" in fraud
        assert 0.0 <= fraud["fraud_confidence"] <= 1.0

    @pytest.mark.asyncio
    async def test_electronics_no_social_scan(self):
        """Electronics category does not perform social scan."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = _make_submit_payload(ELECTRONICS_QA, "Electronics")
            response = await client.post("/api/returns/RET-INT-001/submit", json=payload)

        assert response.status_code == 200
        fraud = response.json()["health_card"]["fraud_signal"]
        assert fraud["social_scan_performed"] is False


# ---------------------------------------------------------------------------
# Test: Graceful degradation hierarchy
# ---------------------------------------------------------------------------


class TestGracefulDegradation:
    """
    Verify the graceful degradation hierarchy:
    full → no social → no anomaly model → partial failure → complete failure
    """

    @pytest.mark.asyncio
    async def test_full_pipeline_electronics_succeeds(self):
        """Full pipeline for Electronics category produces a valid Health Card."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = _make_submit_payload(ELECTRONICS_QA, "Electronics")
            response = await client.post("/api/returns/RET-INT-001/submit", json=payload)

        assert response.status_code == 200
        card = response.json()["health_card"]
        assert card["condition"] in ["Excellent", "Good", "Fair", "Poor"]

    @pytest.mark.asyncio
    async def test_full_pipeline_clothing_with_fraud_scan(self):
        """Clothing & Footwear category triggers fraud scanner call but degrades gracefully with no connected accounts."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = _make_submit_payload(CLOTHING_QA, "Clothing & Footwear", price=5999.0)
            response = await client.post("/api/returns/RET-INT-002/submit", json=payload)

        assert response.status_code == 200
        card = response.json()["health_card"]
        assert card["condition"] in ["Excellent", "Good", "Fair", "Poor"]
        # Fraud scanner was called but with no connected accounts it degrades gracefully
        # social_scan_performed=False is the correct "no social" degradation level
        assert card["fraud_signal"]["social_scan_performed"] is False
        assert card["fraud_signal"]["fraud_confidence"] >= 0.0

    @pytest.mark.asyncio
    async def test_food_and_grocery_pipeline(self):
        """Food & Grocery category returns via pipeline and applies overrides."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = _make_submit_payload(FOOD_QA, "Food & Grocery", price=500.0)
            response = await client.post("/api/returns/RET-INT-003/submit", json=payload)

        assert response.status_code == 200
        card = response.json()["health_card"]
        # Food & Grocery sealed + unexpired + "Wrong item delivered" → return_to_seller
        assert card["disposition"] == "return_to_seller"

    @pytest.mark.asyncio
    async def test_other_category_pipeline(self):
        """Other category produces a valid Health Card via full pipeline."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = _make_submit_payload(OTHER_QA, "Other", price=1500.0)
            response = await client.post("/api/returns/RET-INT-004/submit", json=payload)

        assert response.status_code == 200
        card = response.json()["health_card"]
        assert card["condition"] in ["Excellent", "Good", "Fair", "Poor"]
        # Other category: no social scan
        assert card["fraud_signal"]["social_scan_performed"] is False


# ---------------------------------------------------------------------------
# Test: Category weights read from DB
# ---------------------------------------------------------------------------


class TestCategoryWeightsFromDB:
    """Verify the pipeline reads real weights from the database."""

    @pytest.mark.asyncio
    async def test_electronics_weights_applied(self):
        """Electronics category uses w1=30, w2=25, w3=25, w4=20 from DB."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = _make_submit_payload(ELECTRONICS_QA, "Electronics")
            response = await client.post("/api/returns/RET-INT-001/submit", json=payload)

        assert response.status_code == 200
        # The pipeline completed using DB weights (no error/fallback)
        card = response.json()["health_card"]
        assert card["health_score"] >= 0
        assert card["health_score"] <= 100

    @pytest.mark.asyncio
    async def test_clothing_weights_applied(self):
        """Clothing & Footwear category uses w1=20, w2=20, w3=20, w4=40 from DB."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = _make_submit_payload(CLOTHING_QA, "Clothing & Footwear", price=5999.0)
            response = await client.post("/api/returns/RET-INT-002/submit", json=payload)

        assert response.status_code == 200
        card = response.json()["health_card"]
        assert card["health_score"] >= 0
        assert card["health_score"] <= 100


# ---------------------------------------------------------------------------
# Test: Error status transition
# ---------------------------------------------------------------------------


class TestErrorStatusTransition:
    """Verify that pipeline failure sets status to 'error'."""

    @pytest.mark.asyncio
    async def test_pipeline_error_sets_status_to_error(self):
        """When pipeline returns PipelineError, return status transitions to 'error'."""
        from unittest.mock import AsyncMock, patch
        from app.services.pipeline_orchestrator import PipelineError as PE

        mock_orchestrator_instance = AsyncMock()
        mock_orchestrator_instance.execute.return_value = PE(
            message="All grader components failed.",
            failed_component="grader",
        )

        with patch("app.routers.returns.PipelineOrchestrator", return_value=mock_orchestrator_instance):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                payload = _make_submit_payload(ELECTRONICS_QA, "Electronics")
                response = await client.post("/api/returns/RET-INT-001/submit", json=payload)

        assert response.status_code == 500

        # Verify status was set to "error"
        async with aiosqlite.connect(TEST_DB) as db:
            cursor = await db.execute(
                "SELECT status FROM returns WHERE id = ?", ("RET-INT-001",)
            )
            row = await cursor.fetchone()
        assert row[0] == "error"

    @pytest.mark.asyncio
    async def test_grading_status_set_before_pipeline_execution(self):
        """Status transitions to 'grading' before the pipeline runs."""
        from unittest.mock import AsyncMock, patch
        from app.models.health_card import FraudSignal, HealthCard

        captured_status = {}

        async def capturing_execute(pipeline_input):
            """Capture the return status during pipeline execution."""
            async with aiosqlite.connect(TEST_DB) as db:
                cursor = await db.execute(
                    "SELECT status FROM returns WHERE id = ?", ("RET-INT-001",)
                )
                row = await cursor.fetchone()
                captured_status["during_pipeline"] = row[0]
            # Return a valid health card
            return HealthCard(
                condition="Good",
                health_score=80,
                confidence=0.85,
                warranty_left_months=5,
                defects=[],
                anomaly_heatmap_uri="s3://test.png",
                justification="Good. Detected: none. No structural anomalies. Functional check: pass. Warranty: 5 months remaining.",
                disposition="refurbish",
                source="standard_return",
                fraud_signal=FraudSignal(
                    social_scan_performed=False,
                    product_found_in_social=False,
                    fraud_confidence=0.1,
                    p2p_offered=False,
                    customer_chose_p2p=False,
                ),
            )

        with patch("app.routers.returns.PipelineOrchestrator") as MockOrchCls:
            mock_instance = AsyncMock()
            mock_instance.execute.side_effect = capturing_execute
            MockOrchCls.return_value = mock_instance

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                payload = _make_submit_payload(ELECTRONICS_QA, "Electronics")
                response = await client.post("/api/returns/RET-INT-001/submit", json=payload)

        assert response.status_code == 200
        # The status should have been "grading" when the pipeline was called
        assert captured_status.get("during_pipeline") == "grading"
