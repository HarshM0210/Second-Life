"""Unit tests for ReturnWindowValidator service."""

import os
from datetime import date, timedelta
from unittest.mock import patch

import pytest
import pytest_asyncio

from app.config.database import init_db
from app.models.results import ReturnWindowResult
from app.services.exceptions import ServiceError
from app.services.return_window import ReturnWindowValidator

TEST_DB = "test_return_window.db"


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db(monkeypatch):
    """Use a temporary test database with seeded return window data."""
    monkeypatch.setattr("app.config.database.DATABASE_PATH", TEST_DB)
    monkeypatch.setattr("app.services.return_window.DATABASE_PATH", TEST_DB)
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    await init_db()
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


@pytest.fixture
def validator():
    return ReturnWindowValidator()


@pytest.mark.asyncio
async def test_electronics_within_window(validator):
    """Electronics with 30-day window: return on day 10 is eligible."""
    delivery = date.today() - timedelta(days=10)
    result = await validator.validate(delivery, "Electronics")

    assert result.eligible is True
    assert result.window_days == 30
    assert result.days_elapsed == 10
    assert result.expiry_date == delivery + timedelta(days=30)
    assert result.message is None


@pytest.mark.asyncio
async def test_electronics_on_boundary(validator):
    """Electronics: return on exactly day 30 is still eligible."""
    delivery = date.today() - timedelta(days=30)
    result = await validator.validate(delivery, "Electronics")

    assert result.eligible is True
    assert result.window_days == 30
    assert result.days_elapsed == 30
    assert result.message is None


@pytest.mark.asyncio
async def test_electronics_expired(validator):
    """Electronics: return on day 31 is not eligible."""
    delivery = date.today() - timedelta(days=31)
    result = await validator.validate(delivery, "Electronics")

    assert result.eligible is False
    assert result.window_days == 30
    assert result.days_elapsed == 31
    assert result.message is not None
    assert "expired" in result.message.lower()
    assert result.expiry_date.isoformat() in result.message


@pytest.mark.asyncio
async def test_food_grocery_short_window(validator):
    """Food & Grocery has 7-day window: day 8 is expired."""
    delivery = date.today() - timedelta(days=8)
    result = await validator.validate(delivery, "Food & Grocery")

    assert result.eligible is False
    assert result.window_days == 7
    assert result.days_elapsed == 8


@pytest.mark.asyncio
async def test_food_grocery_within_window(validator):
    """Food & Grocery: day 5 is eligible."""
    delivery = date.today() - timedelta(days=5)
    result = await validator.validate(delivery, "Food & Grocery")

    assert result.eligible is True
    assert result.window_days == 7
    assert result.days_elapsed == 5


@pytest.mark.asyncio
async def test_clothing_footwear_window(validator):
    """Clothing & Footwear has 15-day window."""
    delivery = date.today() - timedelta(days=14)
    result = await validator.validate(delivery, "Clothing & Footwear")

    assert result.eligible is True
    assert result.window_days == 15
    assert result.days_elapsed == 14


@pytest.mark.asyncio
async def test_clothing_footwear_expired(validator):
    """Clothing & Footwear: day 16 is expired."""
    delivery = date.today() - timedelta(days=16)
    result = await validator.validate(delivery, "Clothing & Footwear")

    assert result.eligible is False
    assert result.window_days == 15
    assert result.days_elapsed == 16


@pytest.mark.asyncio
async def test_other_category_window(validator):
    """Other category has 30-day window."""
    delivery = date.today() - timedelta(days=25)
    result = await validator.validate(delivery, "Other")

    assert result.eligible is True
    assert result.window_days == 30


@pytest.mark.asyncio
async def test_unknown_category_uses_default(validator):
    """Unknown category falls back to 30-day default window."""
    delivery = date.today() - timedelta(days=29)
    result = await validator.validate(delivery, "Unknown Category")

    assert result.eligible is True
    assert result.window_days == 30
    assert result.days_elapsed == 29


@pytest.mark.asyncio
async def test_unknown_category_expired_default(validator):
    """Unknown category with default 30-day window: day 31 is expired."""
    delivery = date.today() - timedelta(days=31)
    result = await validator.validate(delivery, "Unknown Category")

    assert result.eligible is False
    assert result.window_days == 30


@pytest.mark.asyncio
async def test_missing_delivery_date_raises_service_error(validator):
    """None delivery_date raises ServiceError with retry message."""
    with pytest.raises(ServiceError) as exc_info:
        await validator.validate(None, "Electronics")

    assert "retry" in exc_info.value.message.lower()
    assert exc_info.value.service == "ReturnWindowValidator"


@pytest.mark.asyncio
async def test_database_error_raises_service_error(validator, monkeypatch):
    """Database connection failure raises ServiceError with retry message."""
    monkeypatch.setattr(
        "app.services.return_window.DATABASE_PATH", "/nonexistent/path/db.sqlite"
    )
    delivery = date.today() - timedelta(days=5)

    with pytest.raises(ServiceError) as exc_info:
        await validator.validate(delivery, "Electronics")

    assert "retry" in exc_info.value.message.lower()


@pytest.mark.asyncio
async def test_same_day_delivery(validator):
    """Delivery today (0 days elapsed) is eligible."""
    delivery = date.today()
    result = await validator.validate(delivery, "Electronics")

    assert result.eligible is True
    assert result.days_elapsed == 0


@pytest.mark.asyncio
async def test_result_is_correct_dataclass(validator):
    """Validate that the result is a proper ReturnWindowResult instance."""
    delivery = date.today() - timedelta(days=3)
    result = await validator.validate(delivery, "Electronics")

    assert isinstance(result, ReturnWindowResult)


@pytest.mark.asyncio
async def test_expiry_date_calculation(validator):
    """Expiry date is delivery_date + window_days."""
    delivery = date.today() - timedelta(days=10)
    result = await validator.validate(delivery, "Food & Grocery")

    expected_expiry = delivery + timedelta(days=7)
    assert result.expiry_date == expected_expiry
