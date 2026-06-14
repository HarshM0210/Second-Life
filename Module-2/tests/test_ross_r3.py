import pytest
from recommend.embedder import embed_text, embed_texts
from recommend.service import load_recommender, load_users

def test_embedding_determinism():
    """R3: Same text -> Same vector."""
    text = "fixed text for determinism"
    v1 = embed_text(text)
    v2 = embed_text(text)
    assert v1 == v2

def test_batch_parity():
    """R3: Batch encoding matches individual encoding (within float tolerance)."""
    texts = ["text one", "text two", "text three"]
    batch = embed_texts(texts)
    indiv = [embed_text(t) for t in texts]
    
    for b, i in zip(batch, indiv):
        assert b == pytest.approx(i, abs=1e-6)

def test_feed_determinism():
    """R3: Same user + same catalog -> same ranking."""
    rec = load_recommender()
    users = load_users()
    user = users["u-priya"]
    
    feed1 = rec.recommend(user, k=10).to_dict()
    feed2 = rec.recommend(user, k=10).to_dict()
    
    assert feed1 == feed2

def test_stable_sort_with_equal_scores():
    """R3: Rankings are stable even with equal scores."""
    from recommend.rerank import rerank
    
    # Mock items with identical scores
    retrieved = [("SKU-B", 0.5), ("SKU-A", 0.5), ("SKU-C", 0.5)]
    cards = {} # no boost
    reasons = {}
    
    feed1 = rerank("u", retrieved, cards, reasons, k=None)
    feed2 = rerank("u", retrieved, cards, reasons, k=None)
    
    assert [i.sku_id for i in feed1.items] == [i.sku_id for i in feed2.items]
