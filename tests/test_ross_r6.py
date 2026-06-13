import pytest
import json
from recommend.service import load_recommender, load_users
from recommend.schemas import UserContext

def test_persona_priya():
    """R6: Verify Priya (Yoga/Nike fan) sees relevant items."""
    rec = load_recommender()
    users = load_users()
    user = users["u-priya"]
    
    feed = rec.recommend(user, k=5)
    
    # Priya has Nike in wishlist
    # Expect Nike items to rank high
    items = [i.sku_id for i in feed.items]
    assert any("NIKE" in s for s in items)
    
    # Check if a Renewed Nike item is boosted
    nike_r = next((i for i in feed.items if i.sku_id == "SKU-NIKE-RUN-8R"), None)
    assert nike_r is not None
    assert nike_r.rank == 1 # Based on snapshot
    assert any("Renewed, health" in r for r in nike_r.reasons)

def test_persona_rahul():
    """R6: Verify Rahul (Parent) sees baby monitor."""
    rec = load_recommender()
    users = load_users()
    user = users["u-rahul"]
    
    feed = rec.recommend(user, k=5)
    
    # Rahul has baby monitor in wishlist
    top_item = feed.items[0]
    assert "BABYMON" in top_item.sku_id
    
    # Rahul should see the Renewed boost
    assert top_item.badge == "Renewed"

def test_persona_small_seller():
    """R6: Small Seller sourcing inventory — trending reasons drive discovery."""
    rec = load_recommender()
    users = load_users()
    user = users["u-seller"]

    feed = rec.recommend(user, k=10)

    # The seller's trends (coffee, yoga) should surface trending reasons.
    trending_items = [i for i in feed.items if any("trending in" in r for r in i.reasons)]
    trending_skus = [i.sku_id for i in trending_items]
    assert "SKU-COFFEE-PRESS" in trending_skus
    assert "SKU-YOGA-MAT" in trending_skus


# Golden snapshot — the demo-facing output. If a change moves these, it must be
# a deliberate, reviewed change (update the golden in the same commit), not an
# accidental ranking drift. Captured 2026-06-13 against the fixtures.
GOLDEN_SNAPSHOT = {
    "u-priya": [
        {"sku_id": "SKU-NIKE-RUN-8R", "rank": 1, "badge": "Renewed"},
        {"sku_id": "SKU-NIKE-RUN-8",  "rank": 2, "badge": "New"},
        {"sku_id": "SKU-YOGA-MAT",    "rank": 3, "badge": "New"},
    ],
    "u-rahul": [
        {"sku_id": "SKU-BABYMON-1R",   "rank": 1, "badge": "Renewed"},
        {"sku_id": "SKU-BABYMON-1",    "rank": 2, "badge": "New"},
        {"sku_id": "SKU-COFFEE-PRESS", "rank": 3, "badge": "New"},
    ],
    "u-coldstart": [
        {"sku_id": "SKU-BABYMON-1R", "rank": 1, "badge": "Renewed"},
        {"sku_id": "SKU-NIKE-RUN-8R", "rank": 2, "badge": "Renewed"},
        {"sku_id": "SKU-BABYMON-1",  "rank": 3, "badge": "New"},
    ],
    "u-seller": [
        {"sku_id": "SKU-COFFEE-PRESS", "rank": 1, "badge": "New"},
        {"sku_id": "SKU-NIKE-RUN-8R",  "rank": 2, "badge": "Renewed"},
        {"sku_id": "SKU-BABYMON-1R",   "rank": 3, "badge": "Renewed"},
    ],
}


def test_snapshot_persona_output():
    """R6: Pin the top-3 feed for every persona against the golden snapshot."""
    rec = load_recommender()
    users = load_users()

    snapshots = {}
    for uid, user in users.items():
        feed = rec.recommend(user, k=3)
        snapshots[uid] = [
            {"sku_id": i.sku_id, "rank": i.rank, "badge": i.badge}
            for i in feed.items
        ]

    print("\nPersona Snapshots (Top 3):")
    print(json.dumps(snapshots, indent=2))

    assert snapshots == GOLDEN_SNAPSHOT, (
        "Persona ranking drifted from the golden snapshot. If intentional, "
        "update GOLDEN_SNAPSHOT in the same commit."
    )
