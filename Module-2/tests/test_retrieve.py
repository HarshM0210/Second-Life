"""Ross — tests for the pure reusable core (Module 5 contract + determinism)."""
import math

import pytest

from recommend.retrieve import cosine_similarity, retrieve


def test_cosine_identical_is_one():
    assert cosine_similarity([1, 2, 3], [1, 2, 3]) == pytest.approx(1.0)


def test_cosine_orthogonal_is_zero():
    assert cosine_similarity([1, 0], [0, 1]) == pytest.approx(0.0)


def test_cosine_zero_vector_is_zero_not_nan():
    val = cosine_similarity([0, 0, 0], [1, 2, 3])
    assert val == 0.0 and not math.isnan(val)


def test_cosine_length_mismatch_raises():
    with pytest.raises(ValueError):
        cosine_similarity([1, 2], [1, 2, 3])


def test_retrieve_is_reusable_with_arbitrary_vectors():
    # The P2P contract: retrieve() works standalone, no recommendation rules.
    user = [1.0, 0.0]
    items = {"a": [1.0, 0.0], "b": [0.0, 1.0], "c": [0.7, 0.7]}
    out = retrieve(user, items)
    assert out[0][0] == "a"          # most similar
    assert out[-1][0] == "b"         # least similar


def test_retrieve_deterministic_tie_break_by_sku():
    user = [1.0, 1.0]
    items = {"z": [1.0, 1.0], "a": [1.0, 1.0]}  # identical similarity
    out = retrieve(user, items)
    assert [s for s, _ in out] == ["a", "z"]    # sku_id asc tiebreak


def test_retrieve_k_caps_results():
    user = [1.0, 0.0]
    items = {f"i{n}": [float(n), 1.0] for n in range(5)}
    assert len(retrieve(user, items, k=2)) == 2
