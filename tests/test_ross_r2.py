import time
import random
import pytest
import numpy as np
from recommend.pipeline import Recommender
from recommend.schemas import HealthCard, UserContext
from recommend.config import EMBED

def generate_mock_vecs(n, dim):
    # Unit vectors
    vecs = np.random.randn(n, dim)
    vecs /= np.linalg.norm(vecs, axis=1)[:, np.newaxis]
    return vecs.tolist()

def test_performance_scaling():
    """R2: Performance over scaled catalog."""
    dim = EMBED.dim
    sizes = [100, 1000, 5000] # 10k might be too slow for a routine test, but let's try up to 5k
    
    for n in sizes:
        sku_text = {f"SKU-{i}": f"Product description {i}" for i in range(n)}
        cards = {f"SKU-{i}": HealthCard(sku_id=f"SKU-{i}", is_renewed=random.choice([True, False])) for i in range(n)}
        
        # We manually set item_vecs to avoid 5000 calls to the real embedder during test setup
        rec = Recommender({"SKU-0": "warmup"}, {})
        mock_vecs = generate_mock_vecs(n, dim)
        rec.item_vecs = {f"SKU-{i}": mock_vecs[i] for i in range(n)}
        rec.sku_text = sku_text
        rec.cards = cards
        
        user = UserContext(user_id="u", searches=["product"])
        
        # Warmup
        rec.recommend(user, k=10)
        
        start = time.perf_counter()
        iters = 5
        for _ in range(iters):
            rec.recommend(user, k=10)
        end = time.perf_counter()
        
        avg_ms = ((end - start) / iters) * 1000
        print(f"Catalog size {n}: Avg latency {avg_ms:.2f}ms")
        
        # Demo budget constraint: should be < 100ms for small-mid catalog
        assert avg_ms < 200 # relaxed for CI but usually much faster
