"""Ross — end-to-end + edge cases + contract conformance against fixtures."""
import json
from pathlib import Path

import pytest

from recommend.pipeline import Recommender
from recommend.schemas import HealthCard, UserContext

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture
def recommender():
    catalog = json.loads((FIXTURES / "catalog.json").read_text())
    cards_raw = json.loads((FIXTURES / "health_cards.json").read_text())
    sku_text = {i["sku_id"]: i["text"] for i in catalog}
    cards = {c["sku_id"]: HealthCard.from_dict(c) for c in cards_raw}
    return Recommender(sku_text, cards)


def test_feed_conforms_to_contract(recommender):
    user = UserContext.from_dict({"user_id": "u", "wishlist": ["SKU-NIKE-RUN-8"]})
    feed = recommender.recommend(user, k=5).to_dict()
    assert feed["user_id"] == "u"
    assert len(feed["items"]) <= 5
    ranks = [i["rank"] for i in feed["items"]]
    assert ranks == sorted(ranks) and ranks[0] == 1  # 1-based, ordered


def test_feed_mixes_new_and_renewed(recommender):
    user = UserContext.from_dict({"user_id": "u", "searches": ["running shoes"]})
    badges = {i.badge for i in recommender.recommend(user).items}
    assert badges <= {"New", "Renewed"}


def test_determinism_same_input_same_order(recommender):
    user = UserContext.from_dict({"user_id": "u", "searches": ["headphones"]})
    a = [i.sku_id for i in recommender.recommend(user).items]
    b = [i.sku_id for i in recommender.recommend(user).items]
    assert a == b


def test_cold_start_user_does_not_crash(recommender):
    user = UserContext.from_dict({"user_id": "cold"})
    feed = recommender.recommend(user)
    assert feed.user_id == "cold"  # returns something, no exception


def test_empty_catalog():
    rec = Recommender(sku_text={}, cards={})
    feed = rec.recommend(UserContext.from_dict({"user_id": "u", "searches": ["x"]}))
    assert feed.items == []


def test_all_new_catalog():
    rec = Recommender(
        sku_text={"a": "thing one", "b": "thing two"},
        cards={},  # no Health Cards -> all treated New
    )
    feed = rec.recommend(UserContext.from_dict({"user_id": "u", "searches": ["thing"]}))
    assert all(i.badge == "New" for i in feed.items)


def test_all_renewed_catalog():
    cards = {
        "a": HealthCard("a", health_score=95, confidence=0.9, is_renewed=True),
        "b": HealthCard("b", health_score=80, confidence=0.9, is_renewed=True),
    }
    rec = Recommender(sku_text={"a": "thing one", "b": "thing two"}, cards=cards)
    feed = rec.recommend(UserContext.from_dict({"user_id": "u", "searches": ["thing"]}))
    assert all(i.badge == "Renewed" for i in feed.items)


def test_tolerates_extra_and_missing_card_fields():
    # Upstream (Module 1) may add/remove fields — we must not break.
    card = HealthCard.from_dict({"sku_id": "x", "health_score": 90, "surprise": "!"})
    assert card.sku_id == "x" and card.is_renewed is False
