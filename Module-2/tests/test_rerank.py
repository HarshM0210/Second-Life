"""Ross — tests for ranking correctness (the module's novel bit) + contract shape."""
from recommend.rerank import rerank
from recommend.schemas import HealthCard


def _card(sku, renewed=False, score=100.0, conf=1.0, price=100, orig=100):
    return HealthCard(
        sku_id=sku, health_score=score, confidence=conf,
        price=price, original_price=orig, is_renewed=renewed,
    )


def test_high_score_renewed_outranks_equal_new():
    # Same retrieval similarity; the >90 Renewed (discounted) must rank up.
    retrieved = [("new", 0.80), ("ren", 0.80)]
    cards = {
        "new": _card("new", renewed=False),
        "ren": _card("ren", renewed=True, score=94, price=70, orig=100),
    }
    feed = rerank("u", retrieved, cards)
    assert feed.items[0].sku_id == "ren"
    assert feed.items[0].badge == "Renewed"
    assert any("Renewed" in r for r in feed.items[0].reasons)


def test_low_health_renewed_gets_no_boost():
    retrieved = [("new", 0.80), ("ren", 0.80)]
    cards = {
        "new": _card("new"),
        "ren": _card("ren", renewed=True, score=40),  # below floor
    }
    feed = rerank("u", retrieved, cards)
    # Tie on score -> deterministic sku_id order, no boost reasons on 'ren'.
    ren = next(i for i in feed.items if i.sku_id == "ren")
    assert ren.score == 0.80
    assert ren.reasons == []


def test_low_confidence_card_gets_no_boost():
    retrieved = [("ren", 0.50)]
    cards = {"ren": _card("ren", renewed=True, score=95, conf=0.10)}
    feed = rerank("u", retrieved, cards)
    assert feed.items[0].score == 0.50


def test_missing_card_treated_as_new():
    retrieved = [("orphan", 0.5)]
    feed = rerank("u", retrieved, cards={})
    assert feed.items[0].badge == "New"
    assert feed.items[0].health_score == 0.0


def test_output_matches_feed_contract():
    retrieved = [("a", 0.9), ("b", 0.5)]
    feed = rerank("u", retrieved, cards={}).to_dict()
    assert set(feed) == {"user_id", "items"}
    first = feed["items"][0]
    assert set(first) == {"sku_id", "rank", "score", "badge", "health_score", "reasons"}
    assert first["rank"] == 1 and feed["items"][1]["rank"] == 2


def test_base_reasons_merged():
    retrieved = [("a", 0.9)]
    feed = rerank("u", retrieved, cards={}, base_reasons={"a": ["matches wishlist"]})
    assert "matches wishlist" in feed.items[0].reasons
