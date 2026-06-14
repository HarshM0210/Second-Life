"""End-to-end API tests exercising the full earn → wallet → redeem flow."""

from __future__ import annotations

from datetime import datetime, timezone


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["service"] == "green_coin"


def test_earn_donate_local(client):
    r = client.post(
        "/api/v4/coins/earn",
        json={
            "user_id": "priya",
            "disposition": "DONATE_LOCAL",
            "category": "footwear",
            "item_id": "shoe-123",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["coins_earned"] > 0
    assert body["co2e_kg"] > 0
    assert body["new_balance"] == body["coins_earned"]
    assert body["equivalents"]["trees_per_month"] >= 0


def test_earn_caps_at_configured_limit(client):
    """A high-CO2e P2P electronics earn is capped at EARN_CAP_PER_EVENT (500)."""
    r = client.post(
        "/api/v4/coins/earn",
        json={
            "user_id": "rahul",
            "disposition": "P2P_LOCAL",
            "category": "electronics",
            "item_id": "monitor-1",
            "buyer_distance_km": 10,
        },
    )
    assert r.status_code == 200
    assert r.json()["coins_earned"] <= 500


def test_wallet_reflects_earns_and_badges(client):
    client.post(
        "/api/v4/coins/earn",
        json={
            "user_id": "u1",
            "disposition": "KEEP",
            "category": "electronics",
            "item_id": "i1",
        },
    )
    r = client.get("/api/v4/coins/wallet/u1")
    assert r.status_code == 200
    body = r.json()
    assert body["balance"] > 0
    assert body["co2e_total_kg"] > 0
    # KEEP electronics ~= 45 kg CO2e -> Seed Saver (5) + Green Guardian (25) unlocked.
    unlocked = {b["slug"] for b in body["badges"] if b["unlocked"]}
    assert "seed_saver" in unlocked
    assert "green_guardian" in unlocked
    assert len(body["history"]) >= 1


def test_redeem_success_and_insufficient(client):
    # Earn a big balance first.
    client.post(
        "/api/v4/coins/earn",
        json={
            "user_id": "buyer",
            "disposition": "P2P_LOCAL",
            "category": "electronics",
            "item_id": "tv",
            "buyer_distance_km": 5,
        },
    )
    ok = client.post(
        "/api/v4/coins/redeem",
        json={"user_id": "buyer", "reward_id": "renewed_discount_100"},
    )
    assert ok.status_code == 200 and ok.json()["success"] is True

    # Redeeming something unaffordable fails cleanly.
    broke = client.post(
        "/api/v4/coins/redeem",
        json={"user_id": "nobody", "reward_id": "prime_1month_1000"},
    )
    assert broke.status_code == 200
    assert broke.json()["success"] is False
    assert broke.json()["reason"] == "insufficient_balance"


def test_redeem_unknown_reward(client):
    r = client.post(
        "/api/v4/coins/redeem",
        json={"user_id": "x", "reward_id": "does_not_exist"},
    )
    assert r.json()["success"] is False
    assert r.json()["reason"] == "unknown_reward"


def test_rewards_catalog(client):
    r = client.get("/api/v4/coins/rewards")
    assert r.status_code == 200
    ids = {x["reward_id"] for x in r.json()}
    assert "renewed_discount_100" in ids


def test_impact_summary_aggregates(client):
    client.post(
        "/api/v4/coins/earn",
        json={
            "user_id": "a",
            "disposition": "DONATE_LOCAL",
            "category": "clothing",
            "item_id": "shirt-1",
        },
    )
    r = client.get("/api/v4/coins/impact/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["items_given_second_life"] >= 1
    assert body["co2e_avoided_kg"] > 0


def test_purchase_avoidance_integration_from_module3(client):
    """Module 3's purchase_avoidance event rewards the kept item with +40."""
    r = client.post(
        "/api/v4/purchase-avoidance",
        json={
            "event_type": "purchase_avoidance",
            "customer_id": "cust-9",
            "product_id": "prod-9",
            "risk_score": 0.82,
            "intervention_type": "SIZE_GUIDANCE",
            "session_id": "sess-1",
            "emitted_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["accepted"] is True
    assert body["coins_earned"] == 40
    assert body["new_balance"] == 40


def test_bonus_earn(client):
    r = client.post(
        "/api/v4/coins/earn/bonus",
        json={"user_id": "b1", "coins": 50, "source": "chose_renewed", "item_id": "r1"},
    )
    assert r.status_code == 200
    assert r.json()["new_balance"] == 50
