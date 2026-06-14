import pytest
from recommend.rerank import rerank, _renewed_boost
from recommend.schemas import HealthCard, FeedItem
from recommend.config import RERANK

def test_missing_card_is_treated_as_new():
    """R7: SKU without a HealthCard should be 'New' with no boost."""
    retrieved = [("SKU-1", 0.8)]
    cards = {} # empty
    feed = rerank("u", retrieved, cards)
    item = feed.items[0]
    assert item.badge == "New"
    assert item.score == 0.8
    assert item.health_score == 0.0

def test_low_confidence_blocks_boost():
    """R7: Low confidence (below min_confidence) should block any boost."""
    card = HealthCard(
        sku_id="R", 
        is_renewed=True, 
        health_score=95, 
        confidence=RERANK.min_confidence - 0.05
    )
    boost, reasons = _renewed_boost(card)
    assert boost == 0.0
    assert len(reasons) == 0

def test_boost_saturation():
    """R7: Boost should saturate at health_score_ceil."""
    # Score 100
    card1 = HealthCard(sku_id="R1", is_renewed=True, health_score=100, confidence=0.9)
    # Score 110 (over ceil)
    card2 = HealthCard(sku_id="R2", is_renewed=True, health_score=110, confidence=0.9)
    
    boost1, _ = _renewed_boost(card1)
    boost2, _ = _renewed_boost(card2)
    
    assert boost1 == boost2
    assert boost1 == pytest.approx(RERANK.renewed_boost_weight)

def test_zero_price_handled_gracefully():
    """R7: Zero or negative price in HealthCard should not crash discount_frac."""
    card = HealthCard(sku_id="R", price=0, original_price=100, is_renewed=True)
    assert card.discount_frac == 0.0
    
    card2 = HealthCard(sku_id="R2", price=50, original_price=0, is_renewed=True)
    assert card2.discount_frac == 0.0
    
    # Valid discount
    card3 = HealthCard(sku_id="R3", price=70, original_price=100, is_renewed=True)
    assert card3.discount_frac == pytest.approx(0.3)
