import pytest
from recommend.retrieve import retrieve

def test_retrieve_pure_function():
    """R5: retrieve() works with arbitrary vectors (Module 5 contract)."""
    # 2D vectors for simplicity
    user = [1.0, 0.0]
    items = {
        "A": [1.0, 0.0],  # sim 1.0
        "B": [0.0, 1.0],  # sim 0.0
        "C": [0.707, 0.707] # sim ~0.707
    }
    
    results = retrieve(user, items)
    
    assert results[0][0] == "A"
    assert results[1][0] == "C"
    assert results[2][0] == "B"
    assert results[0][1] == pytest.approx(1.0)
    assert results[1][1] == pytest.approx(0.707, abs=1e-3)

def test_retrieve_geo_filter_wrapper_smoke():
    """R5: Demonstrate how Module 5 can wrap retrieve() with geo logic."""
    user_vec = [1.0, 1.0]
    item_vecs = {
        "Far": [1.0, 1.0],   # sim 1.0, but far away
        "Near": [1.0, 0.9],  # sim ~1.0, and near
    }
    
    # Mock geo data for Module 5 simulation
    distances = {
        "Far": 500, # km
        "Near": 5   # km
    }
    
    # Module 5 logic:
    raw_results = retrieve(user_vec, item_vecs)
    
    # Apply distance filter (e.g., only items within 10km)
    filtered = [(sid, sim) for sid, sim in raw_results if distances.get(sid, 999) < 10]
    
    assert len(filtered) == 1
    assert filtered[0][0] == "Near"

def test_retrieve_tie_breaking():
    """R5: Ensure deterministic tie-breaking (alpha on SKU)."""
    user = [1.0]
    items = {
        "Z": [1.0],
        "A": [1.0],
        "M": [1.0]
    }
    results = retrieve(user, items)
    # Should be A, M, Z
    assert [r[0] for r in results] == ["A", "M", "Z"]
