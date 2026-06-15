"""
Unit tests for POST /api/returns/initiate endpoint.
"""

import pytest
from datetime import date, timedelta
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.config.database import init_db

import aiosqlite


@pytest.fixture(autouse=True)
async def setup_db(tmp_path, monkeypatch):
    """Set up a temporary database for each test."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr("app.config.database.DATABASE_PATH", db_path)
    monkeypatch.setattr("app.services.return_window.DATABASE_PATH", db_path)
    monkeypatch.setattr("app.routers.returns.get_db", _make_get_db(db_path))
    await init_db()
    yield db_path


def _make_get_db(db_path: str):
    """Create a get_db function that connects to the test db."""

    async def _get_db():
        import aiosqlite

        db = await aiosqlite.connect(db_path)
        db.row_factory = aiosqlite.Row
        return db

    return _get_db


@pytest.fixture
async def client():
    """Create an async HTTP test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_initiate_return_eligible(client, setup_db):
    """Test successful return initiation within the window."""
    delivery_date = (date.today() - timedelta(days=5)).isoformat()
    response = await client.post(
        "/api/returns/initiate",
        json={
            "order_id": "ORD-001",
            "product_id": "PROD-001",
            "customer_id": "CUST-001",
            "delivery_date": delivery_date,
            "category": "Electronics",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["eligible"] is True
    assert data["return_id"].startswith("RET-")
    assert data["window_days"] == 30
    assert data["days_elapsed"] == 5
    assert data["category"] == "Electronics"
    assert len(data["questions"]) > 0
    # Verify first question is return_reason
    assert data["questions"][0]["id"] == "return_reason"


@pytest.mark.asyncio
async def test_initiate_return_expired_window(client, setup_db):
    """Test return initiation when window has expired — should return 403."""
    delivery_date = (date.today() - timedelta(days=40)).isoformat()
    response = await client.post(
        "/api/returns/initiate",
        json={
            "order_id": "ORD-002",
            "product_id": "PROD-002",
            "customer_id": "CUST-002",
            "delivery_date": delivery_date,
            "category": "Electronics",
        },
    )

    assert response.status_code == 403
    data = response.json()["detail"]
    assert data["eligible"] is False
    assert data["return_id"] is None
    assert "expired" in data["message"].lower()
    assert data["expiry_date"] is not None


@pytest.mark.asyncio
async def test_initiate_return_food_category_short_window(client, setup_db):
    """Test that Food & Grocery has a 7-day window."""
    # 8 days ago — should be expired for Food & Grocery
    delivery_date = (date.today() - timedelta(days=8)).isoformat()
    response = await client.post(
        "/api/returns/initiate",
        json={
            "order_id": "ORD-003",
            "product_id": "PROD-003",
            "customer_id": "CUST-003",
            "delivery_date": delivery_date,
            "category": "Food & Grocery",
        },
    )

    assert response.status_code == 403
    data = response.json()["detail"]
    assert data["eligible"] is False


@pytest.mark.asyncio
async def test_initiate_return_food_category_within_window(client, setup_db):
    """Test that Food & Grocery within 7 days is eligible."""
    delivery_date = (date.today() - timedelta(days=5)).isoformat()
    response = await client.post(
        "/api/returns/initiate",
        json={
            "order_id": "ORD-004",
            "product_id": "PROD-004",
            "customer_id": "CUST-004",
            "delivery_date": delivery_date,
            "category": "Food & Grocery",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["eligible"] is True
    assert data["window_days"] == 7
    assert data["category"] == "Food & Grocery"
    # Should get food questions
    assert data["questions"][0]["id"] == "return_reason"


@pytest.mark.asyncio
async def test_initiate_return_clothing_category(client, setup_db):
    """Test Clothing & Footwear category with 15-day window."""
    delivery_date = (date.today() - timedelta(days=10)).isoformat()
    response = await client.post(
        "/api/returns/initiate",
        json={
            "order_id": "ORD-005",
            "product_id": "PROD-005",
            "customer_id": "CUST-005",
            "delivery_date": delivery_date,
            "category": "Clothing & Footwear",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["eligible"] is True
    assert data["window_days"] == 15
    assert data["category"] == "Clothing & Footwear"


@pytest.mark.asyncio
async def test_initiate_return_default_values(client, setup_db):
    """Test with no delivery_date or category — uses defaults."""
    response = await client.post(
        "/api/returns/initiate",
        json={
            "order_id": "ORD-006",
            "product_id": "PROD-006",
            "customer_id": "CUST-006",
        },
    )

    assert response.status_code == 200
    data = response.json()
    # Default: 7 days ago, Electronics — should be eligible
    assert data["eligible"] is True
    assert data["category"] == "Electronics"
    assert data["days_elapsed"] == 7


@pytest.mark.asyncio
async def test_initiate_return_persists_in_db(client, setup_db):
    """Test that an eligible return is persisted in the SQLite database."""
    delivery_date = (date.today() - timedelta(days=3)).isoformat()
    response = await client.post(
        "/api/returns/initiate",
        json={
            "order_id": "ORD-007",
            "product_id": "PROD-007",
            "customer_id": "CUST-007",
            "delivery_date": delivery_date,
            "category": "Electronics",
        },
    )

    assert response.status_code == 200
    data = response.json()
    return_id = data["return_id"]

    # Verify persistence
    async with aiosqlite.connect(setup_db) as db:
        cursor = await db.execute(
            "SELECT id, order_id, product_id, customer_id, category, status FROM returns WHERE id = ?",
            (return_id,),
        )
        row = await cursor.fetchone()

    assert row is not None
    assert row[0] == return_id
    assert row[1] == "ORD-007"
    assert row[2] == "PROD-007"
    assert row[3] == "CUST-007"
    assert row[4] == "Electronics"
    assert row[5] == "initiated"


@pytest.mark.asyncio
async def test_initiate_return_expired_does_not_persist(client, setup_db):
    """Test that an expired return is NOT persisted in the database."""
    delivery_date = (date.today() - timedelta(days=60)).isoformat()
    response = await client.post(
        "/api/returns/initiate",
        json={
            "order_id": "ORD-008",
            "product_id": "PROD-008",
            "customer_id": "CUST-008",
            "delivery_date": delivery_date,
            "category": "Electronics",
        },
    )

    assert response.status_code == 403

    # Verify nothing persisted
    async with aiosqlite.connect(setup_db) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM returns WHERE order_id = ?",
            ("ORD-008",),
        )
        row = await cursor.fetchone()

    assert row[0] == 0


@pytest.mark.asyncio
async def test_initiate_return_questions_have_correct_structure(client, setup_db):
    """Test that returned questions have the expected structure."""
    delivery_date = (date.today() - timedelta(days=2)).isoformat()
    response = await client.post(
        "/api/returns/initiate",
        json={
            "order_id": "ORD-009",
            "product_id": "PROD-009",
            "customer_id": "CUST-009",
            "delivery_date": delivery_date,
            "category": "Electronics",
        },
    )

    assert response.status_code == 200
    data = response.json()
    questions = data["questions"]

    for q in questions:
        assert "id" in q
        assert "text" in q
        assert "options" in q
        assert isinstance(q["options"], list)
        # supplementary_input and conditional_display can be None
        assert "supplementary_input" in q
        assert "conditional_display" in q


@pytest.mark.asyncio
async def test_initiate_return_boundary_day_equals_window(client, setup_db):
    """Test that delivery exactly at the window boundary is still eligible."""
    # Electronics window is 30 days — exactly 30 days should be eligible
    delivery_date = (date.today() - timedelta(days=30)).isoformat()
    response = await client.post(
        "/api/returns/initiate",
        json={
            "order_id": "ORD-010",
            "product_id": "PROD-010",
            "customer_id": "CUST-010",
            "delivery_date": delivery_date,
            "category": "Electronics",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["eligible"] is True
    assert data["days_elapsed"] == 30
    assert data["window_days"] == 30
