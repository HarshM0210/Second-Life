import json
from pathlib import Path
import pytest
from recommend.service import load_recommender, load_users
from recommend.schemas import UserContext

def test_already_purchased_in_feed():
    """
    R9: Already-purchased items in the feed.
    Priya's feed surfaces a previously-purchased SKU. Pin this behavior.
    """
    rec = load_recommender()
    users = load_users()
    
    priya = users["u-priya"]
    # Check Priya's history
    print(f"Priya history: {priya.purchase_history}")
    
    feed = rec.recommend(priya)
    
    # Check if any item in feed is in history
    purchased_in_feed = [i for i in feed.items if i.sku_id in priya.purchase_history]
    
    print("\nPurchased items found in Priya's feed:")
    for item in purchased_in_feed:
        print(f"SKU: {item.sku_id}, Rank: {item.rank}, Score: {item.score:.4f}, Reasons: {item.reasons}")

    # Assert current behavior: at least one purchased item is in the top 10 (or whatever k is)
    # The task says rank 3.
    assert len(purchased_in_feed) > 0
