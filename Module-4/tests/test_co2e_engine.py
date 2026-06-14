"""Unit tests for the pure CO2e + coin math."""

from __future__ import annotations

import pytest

from green_coin.core.co2e_engine import (
    Disposition,
    baseline_co2e,
    co2e_avoided,
    coins_earned,
    equivalents,
)


def test_baseline_is_positive():
    assert baseline_co2e(0.5) == pytest.approx(0.5 * 300 * (0.089 / 1000))


def test_return_fc_has_zero_avoidance():
    assert co2e_avoided(Disposition.RETURN_FC, "electronics") == 0.0


def test_unknown_disposition_is_zero():
    assert co2e_avoided("SOMETHING_ELSE", "electronics") == 0.0


def test_p2p_local_beats_the_processing_paths():
    """P2P local should beat the refurbish/resell/donate/recycle paths.

    (KEEP is the only path marginally higher, since P2P subtracts a small
    buyer-transport term — consistent with the README's formula.)
    """
    kwargs = dict(category="electronics", item_weight_kg=0.5, buyer_distance_km=10)
    p2p = co2e_avoided(Disposition.P2P_LOCAL, **kwargs)
    processing = [
        co2e_avoided(d, **kwargs)
        for d in (
            Disposition.REFURBISH,
            Disposition.RESELL,
            Disposition.DONATE_LOCAL,
            Disposition.RECYCLE,
        )
    ]
    assert all(p2p > o for o in processing)


def test_enum_and_string_forms_agree():
    a = co2e_avoided(Disposition.DONATE_LOCAL, "footwear")
    b = co2e_avoided("DONATE_LOCAL", "footwear")
    assert a == b


def test_unknown_category_uses_default_factor():
    known = co2e_avoided(Disposition.KEEP, "electronics")
    unknown = co2e_avoided(Disposition.KEEP, "nonexistent_category")
    assert known != unknown  # electronics factor (45) != default (10)


def test_coins_never_negative():
    assert coins_earned(-5.0) == 0
    assert coins_earned(0.0) == 0


def test_coins_scale_with_multiplier():
    assert coins_earned(3.0, multiplier=10) == 30
    assert coins_earned(3.0, multiplier=20) == 60


def test_equivalents_are_proportional():
    eq = equivalents(8.3)
    assert eq["trees_per_month"] == pytest.approx(10.0, abs=0.1)
