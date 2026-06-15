"""
Unit tests for POST /api/returns/{return_id}/p2p-choice endpoint.

Tests Requirements: 15.1, 15.2, 15.3, 15.4, 15.5
"""

import json
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.config.database import init_db
from app.main import app

import os


@pytest.fixture(autouse=True)
async def setup_db(tmp_path, monkeypatch):
    """Initialize a temporary database before each test."""
    db_path = str(tmp_path / "test_p2p.db")
    monkeypatch.setattr("app.config.database.DATABASE_PATH", db_path)
    await init_db()
    yield db_path


@pytest.fixture
def sample_health_card():
    """A sample Health Card JSON to seed in the DB."""
    return {
        "condition": "Good",
        "health_score": 78,
        "confidence": 0.88,
        "warranty_left_months": 3,
        "defects": ["minor scratch on rear casing"],
        "anomaly_heatmap_uri": "s3://bucket/item123_heatmap.png",
        "justification": "Good. Detected: minor scratch (rear casing). No structural anomalies. Functional check: pass. Warranty: 3 months remaining.",
        "disposition": "refurbish",
        "source": "standard_return",
        "fraud_signal": {
            "social_scan_performed": True,
            "product_found_in_social": True,
            "fraud_confidence": 0.72,
            "p2p_offered": False,
            "customer_chose_p2p": False,
        },
    }


async def _seed_return_and_health_card(return_id: str, health_card_data: dict):
    """Helper to seed a return session and health card in SQLite."""
    import aiosqlite
    from app.config.database import DATABASE_PATH

    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            """INSERT INTO returns (id, order_id, product_id, customer_id, category, delivery_date, initiated_at, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                return_id,
                "ORD-001",
                "PROD-001",
                "CUST-001",
                "Clothing & Footwear",
                "2026-01-01",
                "2026-01-05T12:00:00",
                "complete",
            ),
        )
        health_card_id = str(uuid.uuid4())
        await db.execute(
            "INSERT INTO health_cards (id, return_id, health_card_json) VALUES (?, ?, ?)",
            (health_card_id, return_id, json.dumps(health_card_data)),
        )
        await db.commit()


@pytest.fixture
def async_client():
    """Create an async HTTP test client."""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


class TestP2PChoiceEndpoint:
    """Tests for POST /api/returns/{return_id}/p2p-choice."""

    async def test_chose_p2p_true_updates_source(self, async_client, sample_health_card):
        """When chose_p2p=True, source should be 'p2p_fraud_divert'."""
        return_id = "RET-test001"
        await _seed_return_and_health_card(return_id, sample_health_card)

        async with async_client as client:
            response = await client.post(
                f"/api/returns/{return_id}/p2p-choice",
                json={"chose_p2p": True},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["health_card"]["source"] == "p2p_fraud_divert"

    async def test_chose_p2p_true_sets_customer_chose_p2p(self, async_client, sample_health_card):
        """When chose_p2p=True, fraud_signal.customer_chose_p2p should be True."""
        return_id = "RET-test002"
        await _seed_return_and_health_card(return_id, sample_health_card)

        async with async_client as client:
            response = await client.post(
                f"/api/returns/{return_id}/p2p-choice",
                json={"chose_p2p": True},
            )

        assert response.status_code == 200
        fraud_signal = response.json()["health_card"]["fraud_signal"]
        assert fraud_signal["customer_chose_p2p"] is True
        assert fraud_signal["p2p_offered"] is True

    async def test_chose_p2p_false_keeps_standard_source(self, async_client, sample_health_card):
        """When chose_p2p=False, source should remain 'standard_return'."""
        return_id = "RET-test003"
        await _seed_return_and_health_card(return_id, sample_health_card)

        async with async_client as client:
            response = await client.post(
                f"/api/returns/{return_id}/p2p-choice",
                json={"chose_p2p": False},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["health_card"]["source"] == "standard_return"

    async def test_chose_p2p_false_sets_enhanced_inspection(self, async_client, sample_health_card):
        """When chose_p2p=False, enhanced_inspection flag should be added."""
        return_id = "RET-test004"
        await _seed_return_and_health_card(return_id, sample_health_card)

        async with async_client as client:
            response = await client.post(
                f"/api/returns/{return_id}/p2p-choice",
                json={"chose_p2p": False},
            )

        assert response.status_code == 200
        data = response.json()["health_card"]
        assert "flags" in data
        assert "enhanced_inspection" in data["flags"]

    async def test_chose_p2p_false_sets_fraud_signal_fields(self, async_client, sample_health_card):
        """When chose_p2p=False, p2p_offered=True and customer_chose_p2p=False."""
        return_id = "RET-test005"
        await _seed_return_and_health_card(return_id, sample_health_card)

        async with async_client as client:
            response = await client.post(
                f"/api/returns/{return_id}/p2p-choice",
                json={"chose_p2p": False},
            )

        assert response.status_code == 200
        fraud_signal = response.json()["health_card"]["fraud_signal"]
        assert fraud_signal["customer_chose_p2p"] is False
        assert fraud_signal["p2p_offered"] is True

    async def test_nonexistent_return_returns_404(self, async_client):
        """Should return 404 when no health card exists for the return ID."""
        async with async_client as client:
            response = await client.post(
                "/api/returns/RET-nonexistent/p2p-choice",
                json={"chose_p2p": True},
            )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    async def test_persists_updated_health_card(self, async_client, sample_health_card):
        """The updated health card should be persisted in SQLite."""
        return_id = "RET-test006"
        await _seed_return_and_health_card(return_id, sample_health_card)

        async with async_client as client:
            await client.post(
                f"/api/returns/{return_id}/p2p-choice",
                json={"chose_p2p": True},
            )

        # Verify in the database directly
        import aiosqlite
        from app.config.database import DATABASE_PATH

        async with aiosqlite.connect(DATABASE_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT health_card_json FROM health_cards WHERE return_id = ?",
                (return_id,),
            )
            row = await cursor.fetchone()
            assert row is not None
            persisted_card = json.loads(row["health_card_json"])
            assert persisted_card["source"] == "p2p_fraud_divert"
            assert persisted_card["fraud_signal"]["customer_chose_p2p"] is True

    async def test_invalid_request_body_returns_422(self, async_client, sample_health_card):
        """Request without chose_p2p should return 422 validation error."""
        return_id = "RET-test007"
        await _seed_return_and_health_card(return_id, sample_health_card)

        async with async_client as client:
            response = await client.post(
                f"/api/returns/{return_id}/p2p-choice",
                json={},
            )

        assert response.status_code == 422

    async def test_enhanced_inspection_not_duplicated(self, async_client, sample_health_card):
        """Calling with chose_p2p=False twice should not duplicate the flag."""
        return_id = "RET-test008"
        await _seed_return_and_health_card(return_id, sample_health_card)

        async with async_client as client:
            # First call
            await client.post(
                f"/api/returns/{return_id}/p2p-choice",
                json={"chose_p2p": False},
            )
            # Second call
            response = await client.post(
                f"/api/returns/{return_id}/p2p-choice",
                json={"chose_p2p": False},
            )

        assert response.status_code == 200
        flags = response.json()["health_card"]["flags"]
        assert flags.count("enhanced_inspection") == 1
