"""
Unit tests for return_prevention/integrations/customer_profile.py
and return_prevention/integrations/green_coin.py

Tests cover:
- CustomerProfileClient: mock httpx 200 response → returns parsed dict
- CustomerProfileClient: mock timeout → returns None and logs warning
- GreenCoinEmitter: mock 503 on first attempt, 200 on retry → no retry log entry
- GreenCoinEmitter: mock 503 on both attempts → retry log has exactly one JSONL entry

Requirements: 9.2, 8.4
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from return_prevention.integrations.customer_profile import CustomerProfileClient
from return_prevention.integrations.green_coin import GreenCoinEmitter
from return_prevention.schemas.events import PurchaseAvoidanceEvent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CUSTOMER_PROFILE_FIXTURE = {
    "customer_id": "cust-123",
    "order_history": [
        {
            "order_id": "ORD-001",
            "product_id": "prod-abc",
            "category": "Apparel",
            "subcategory": "Men's Jeans",
            "brand": "Levi's",
            "purchased_size": "32",
            "price": 1200.0,
            "seller_id": "seller-01",
            "status": "completed",
            "return_reason": None,
            "order_date": "2025-06-01T10:00:00Z",
        }
    ],
}


@pytest.fixture
def sample_event() -> PurchaseAvoidanceEvent:
    """Return a sample PurchaseAvoidanceEvent for testing."""
    return PurchaseAvoidanceEvent(
        event_type="purchase_avoidance",
        customer_id="cust-123",
        product_id="prod-abc",
        risk_score=0.85,
        intervention_type="SIZE_GUIDANCE",
        session_id="session-xyz",
        emitted_at=datetime(2025, 7, 20, 14, 0, 0, tzinfo=timezone.utc),
    )


# ---------------------------------------------------------------------------
# CustomerProfileClient Tests
# ---------------------------------------------------------------------------


class TestCustomerProfileClientSuccess:
    """CustomerProfileClient returns parsed dict on successful 200 response."""

    @pytest.mark.asyncio
    async def test_get_returns_parsed_dict_on_200(self):
        """Mock httpx to return 200 with fixture data → get() returns parsed dict."""
        mock_response = httpx.Response(
            status_code=200,
            json=CUSTOMER_PROFILE_FIXTURE,
            request=httpx.Request("GET", "http://localhost:8001/api/v2/customer-profile/cust-123"),
        )

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            client = CustomerProfileClient(base_url="http://localhost:8001")
            result = await client.get("cust-123")

        assert result is not None
        assert result == CUSTOMER_PROFILE_FIXTURE
        assert result["customer_id"] == "cust-123"
        assert len(result["order_history"]) == 1
        assert result["order_history"][0]["order_id"] == "ORD-001"


class TestCustomerProfileClientTimeout:
    """CustomerProfileClient returns None and logs warning on timeout."""

    @pytest.mark.asyncio
    async def test_get_returns_none_on_timeout(self, caplog):
        """Mock httpx timeout → get() returns None and logs structured warning."""
        with patch(
            "httpx.AsyncClient.get",
            new_callable=AsyncMock,
            side_effect=httpx.TimeoutException("Connection timed out"),
        ):
            client = CustomerProfileClient(base_url="http://localhost:8001")

            with caplog.at_level(logging.WARNING):
                result = await client.get("cust-456")

        assert result is None
        # Verify structured warning was logged
        assert any("customer_profile_unavailable" in record.message for record in caplog.records)
        assert any("cust-456" in record.message for record in caplog.records)


# ---------------------------------------------------------------------------
# GreenCoinEmitter Tests
# ---------------------------------------------------------------------------


class TestGreenCoinEmitterRetrySuccess:
    """GreenCoinEmitter: 503 on first attempt, 200 on retry → no retry log entry."""

    @pytest.mark.asyncio
    async def test_503_then_200_no_retry_log(self, sample_event, tmp_path, monkeypatch):
        """First attempt returns 503, retry returns 200 → no retry log file written."""
        import return_prevention.integrations.green_coin as gc_module

        # Mock the retry delay to 0 so we don't wait
        monkeypatch.setattr(gc_module, "_RETRY_DELAY_SECONDS", 0)

        # Point the retry log to a temp path
        retry_log_path = tmp_path / "purchase_avoidance_retry.log"
        monkeypatch.setattr(gc_module, "_RETRY_LOG_PATH", retry_log_path)

        # Build responses: first call = 503, second call = 200
        request = httpx.Request("POST", "http://localhost:8002/api/v4/purchase-avoidance")
        response_503 = httpx.Response(status_code=503, request=request)
        response_200 = httpx.Response(status_code=200, request=request)

        call_count = 0

        async def mock_post(self, url, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx.HTTPStatusError(
                    "Server Error", request=request, response=response_503
                )
            return response_200

        with patch("httpx.AsyncClient.post", mock_post):
            emitter = GreenCoinEmitter()
            await emitter.emit(sample_event)

        # Retry log should not exist (second attempt succeeded)
        assert not retry_log_path.exists()
        assert call_count == 2


class TestGreenCoinEmitterBothFail:
    """GreenCoinEmitter: 503 on both attempts → retry log has exactly one JSONL entry."""

    @pytest.mark.asyncio
    async def test_503_both_attempts_writes_retry_log(self, sample_event, tmp_path, monkeypatch):
        """Both attempts return 503 → retry log file has exactly one JSONL entry."""
        import return_prevention.integrations.green_coin as gc_module

        # Mock the retry delay to 0 so we don't wait
        monkeypatch.setattr(gc_module, "_RETRY_DELAY_SECONDS", 0)

        # Point the retry log to a temp path
        retry_log_path = tmp_path / "purchase_avoidance_retry.log"
        monkeypatch.setattr(gc_module, "_RETRY_LOG_PATH", retry_log_path)

        # Both calls return 503
        request = httpx.Request("POST", "http://localhost:8002/api/v4/purchase-avoidance")
        response_503 = httpx.Response(status_code=503, request=request)

        async def mock_post(self, url, **kwargs):
            raise httpx.HTTPStatusError(
                "Server Error", request=request, response=response_503
            )

        with patch("httpx.AsyncClient.post", mock_post):
            emitter = GreenCoinEmitter()
            await emitter.emit(sample_event)

        # Retry log should exist with exactly one entry
        assert retry_log_path.exists()
        lines = retry_log_path.read_text().strip().split("\n")
        assert len(lines) == 1

        # Verify the JSONL entry is valid JSON with expected fields
        entry = json.loads(lines[0])
        assert entry["event_type"] == "purchase_avoidance"
        assert entry["customer_id"] == "cust-123"
        assert entry["product_id"] == "prod-abc"
        assert entry["risk_score"] == 0.85
        assert entry["intervention_type"] == "SIZE_GUIDANCE"
        assert entry["session_id"] == "session-xyz"
