import pytest
from recommend.pipeline import Recommender
from recommend.schemas import HealthCard, UserContext, Feed
from recommend.config import EMBED

@pytest.fixture
def base_rec():
    sku_text = {"SKU-1": "Nike running shoes", "SKU-2": "Video baby monitor"}
    cards = {"SKU-1": HealthCard(sku_id="SKU-1", is_renewed=False)}
    return Recommender(sku_text, cards)

def test_malformed_health_cards():
    """R1: Tolerate malformed health cards (handled by schema but verify pipeline)."""
    # missing fields, wrong types
    bad_card_data = {"sku_id": "SKU-BAD", "health_score": "not a number", "extra": "ignored"}
    card = HealthCard.from_dict(bad_card_data)
    assert card.health_score == 0.0
    assert card.sku_id == "SKU-BAD"
    
    rec = Recommender({"SKU-BAD": "some text"}, {"SKU-BAD": card})
    user = UserContext(user_id="u", searches=["some text"])
    feed = rec.recommend(user)
    assert len(feed.items) == 1
    assert feed.items[0].sku_id == "SKU-BAD"

def test_huge_wishlist_and_history(base_rec):
    """R1: Performance/sanity with large user context."""
    # 1000 items in history/wishlist
    huge_list = [f"SKU-W-{i}" for i in range(1000)]
    user = UserContext(user_id="u", wishlist=huge_list, purchase_history=huge_list)
    
    # Should not crash, even if SKUs aren't in catalog
    feed = base_rec.recommend(user, k=10)
    assert len(feed.items) <= 2
    assert feed.user_id == "u"

def test_unicode_and_empty_searches(base_rec):
    """R1: Emoji and empty strings."""
    user = UserContext(user_id="u", searches=["", "🏃‍♂️👟", "   ", "\0"])
    feed = base_rec.recommend(user)
    assert isinstance(feed, Feed)
    assert len(feed.items) > 0

def test_duplicate_skus_in_context(base_rec):
    """R1: Duplicates should be handled gracefully."""
    user = UserContext(
        user_id="u", 
        wishlist=["SKU-1", "SKU-1", "SKU-1"],
        purchase_history=["SKU-1", "SKU-1"]
    )
    feed = base_rec.recommend(user)
    item = next(i for i in feed.items if i.sku_id == "SKU-1")
    # Should have reasons, no crash
    assert "matches wishlist" in item.reasons
    assert "previously purchased" in item.reasons

def test_sku_in_wishlist_and_history(base_rec):
    """R1: SKU in both wishlist and history."""
    user = UserContext(user_id="u", wishlist=["SKU-1"], purchase_history=["SKU-1"])
    feed = base_rec.recommend(user)
    item = next(i for i in feed.items if i.sku_id == "SKU-1")
    assert "matches wishlist" in item.reasons
    assert "previously purchased" in item.reasons
