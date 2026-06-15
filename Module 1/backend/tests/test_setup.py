"""Tests for project setup and database initialization."""

import os
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.config.database import init_db, get_db, DATABASE_PATH
from app.main import app

TEST_DB = "test_second_life.db"


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db(monkeypatch):
    """Use a temporary test database."""
    monkeypatch.setattr("app.config.database.DATABASE_PATH", TEST_DB)
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    await init_db()
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


@pytest.mark.asyncio
async def test_health_endpoint():
    """Health check endpoint should return ok status."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["module"] == "grading-fraud-quality"


@pytest.mark.asyncio
async def test_database_tables_created():
    """All required tables should exist after initialization."""
    import aiosqlite

    async with aiosqlite.connect(TEST_DB) as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in await cursor.fetchall()]

    expected = ["category_weights", "cost_lookup", "health_cards", "return_windows", "returns"]
    assert tables == expected


@pytest.mark.asyncio
async def test_return_windows_seeded():
    """Return windows table should have default configuration."""
    import aiosqlite

    async with aiosqlite.connect(TEST_DB) as db:
        cursor = await db.execute("SELECT category, window_days FROM return_windows ORDER BY category")
        rows = await cursor.fetchall()

    windows = {row[0]: row[1] for row in rows}
    assert windows["Food & Grocery"] == 7
    assert windows["Electronics"] == 30
    assert windows["Clothing & Footwear"] == 15
    assert windows["Other"] == 30


@pytest.mark.asyncio
async def test_category_weights_seeded():
    """Category weights table should have default configuration."""
    import aiosqlite

    async with aiosqlite.connect(TEST_DB) as db:
        cursor = await db.execute(
            "SELECT category, w1_anomaly, w2_defect, w3_reason, w4_wear FROM category_weights ORDER BY category"
        )
        rows = await cursor.fetchall()

    weights = {row[0]: (row[1], row[2], row[3], row[4]) for row in rows}
    assert weights["Food & Grocery"] == (20.0, 30.0, 30.0, 20.0)
    assert weights["Electronics"] == (30.0, 25.0, 25.0, 20.0)
    assert weights["Clothing & Footwear"] == (20.0, 20.0, 20.0, 40.0)
    assert weights["Other"] == (25.0, 25.0, 25.0, 25.0)


@pytest.mark.asyncio
async def test_cost_lookup_seeded():
    """Cost lookup table should have default processing costs with generated total."""
    import aiosqlite

    async with aiosqlite.connect(TEST_DB) as db:
        cursor = await db.execute(
            "SELECT category, total_processing_cost FROM cost_lookup ORDER BY category"
        )
        rows = await cursor.fetchall()

    costs = {row[0]: row[1] for row in rows}
    assert costs["Food & Grocery"] == 95.0  # 50 + 20 + 10 + 15
    assert costs["Electronics"] == 750.0  # 200 + 150 + 300 + 100
    assert costs["Clothing & Footwear"] == 220.0  # 80 + 50 + 60 + 30
    assert costs["Other"] == 325.0  # 100 + 75 + 100 + 50


@pytest.mark.asyncio
async def test_idempotent_initialization():
    """Running init_db multiple times should not duplicate seed data."""
    import aiosqlite

    # Run init again (already ran in fixture)
    os.environ["DATABASE_PATH"] = TEST_DB
    await init_db()

    async with aiosqlite.connect(TEST_DB) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM return_windows")
        count = (await cursor.fetchone())[0]

    assert count == 4  # Still only 4 categories
