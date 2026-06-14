"""Tests for the /api/v2/customer-profile endpoint consumed by Module 3.

The contract: known customers return their stored order_history; unknown
customers return a valid empty profile with HTTP 200 (never 404), because
Module 3's client only catches transport errors and would otherwise raise.
"""
from fastapi.testclient import TestClient

from recommend import service


def _client() -> TestClient:
    # Trigger the lifespan so the customer-profile store is loaded.
    return TestClient(service.app)


def test_known_customer_returns_order_history():
    with _client() as c:
        r = c.get("/api/v2/customer-profile/CUST-PRIYA")
        assert r.status_code == 200
        body = r.json()
        assert body["customer_id"] == "CUST-PRIYA"
        assert isinstance(body["order_history"], list)
        assert len(body["order_history"]) >= 1
        # Module 3 reads subcategory + status from each order.
        first = body["order_history"][0]
        assert "subcategory" in first
        assert "status" in first


def test_unknown_customer_returns_empty_profile_not_404():
    with _client() as c:
        r = c.get("/api/v2/customer-profile/NOPE-DOES-NOT-EXIST")
        assert r.status_code == 200
        body = r.json()
        assert body == {"customer_id": "NOPE-DOES-NOT-EXIST", "order_history": []}
