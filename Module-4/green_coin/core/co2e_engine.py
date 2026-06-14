"""
green_coin/core/co2e_engine.py

The scientific backbone of Module 4: convert a return disposition into the
kg CO2e avoided versus the default "ship back to FC" baseline, then into
Green Coins.

Pure functions only — no I/O, no DB, no globals mutated. This makes the
engine trivially unit-testable and safe to call from request handlers.

Emission factors are grounded in published data (GLEC Framework / ISO 14083
for transport; LCA literature / ecoinvent for manufacture avoidance). They
are intentionally a lookup table for the prototype; the production roadmap
replaces them with per-SKU LCA data.
"""

from __future__ import annotations

from enum import Enum

# ---------------------------------------------------------------------------
# Dispositions
# ---------------------------------------------------------------------------


class Disposition(str, Enum):
    """Where a returned/unused item is routed.

    ``RETURN_FC`` is the baseline (ship back to a fulfilment centre) and earns
    zero coins by definition — everything else is measured as avoidance
    relative to it.
    """

    P2P_LOCAL = "P2P_LOCAL"
    DONATE_LOCAL = "DONATE_LOCAL"
    KEEP = "KEEP"
    REFURBISH = "REFURBISH"
    RESELL = "RESELL"
    RECYCLE = "RECYCLE"
    RETURN_FC = "RETURN_FC"


# ---------------------------------------------------------------------------
# Emission factors and baseline
# ---------------------------------------------------------------------------

# Road freight, India (GLEC framework): ~0.089 kg CO2e per tonne-km,
# expressed here per kg-km.
EF_ROAD_KG_PER_KG_KM: float = 0.089 / 1000

# Baseline: ship the item back to an FC (assume 300 km average one-way).
BASELINE_DISTANCE_KM: float = 300.0
BASELINE_ITEM_WEIGHT_KG: float = 0.5  # configurable per category

# Manufacture avoidance factors — kg CO2e saved by reusing instead of buying
# a new equivalent (LCA literature, ecoinvent class figures).
MANUFACTURE_AVOIDED: dict[str, float] = {
    "electronics": 45.0,  # smartphone/tablet-class item
    "appliances": 30.0,
    "clothing": 12.0,
    "footwear": 8.0,
    "toys": 5.0,
    "books": 1.5,
    "default": 10.0,
}

# 1 kg CO2e avoided == COIN_MULTIPLIER Green Coins (tunable per business need;
# the live value is read from config and passed in by callers).
COIN_MULTIPLIER: int = 10


def baseline_co2e(item_weight_kg: float = BASELINE_ITEM_WEIGHT_KG) -> float:
    """CO2e (kg) of the default 'ship back to FC' path."""
    return item_weight_kg * BASELINE_DISTANCE_KM * EF_ROAD_KG_PER_KG_KM


def co2e_avoided(
    disposition: str,
    category: str,
    item_weight_kg: float = BASELINE_ITEM_WEIGHT_KG,
    buyer_distance_km: float = 0.0,
) -> float:
    """Return kg CO2e avoided versus the warehouse-return baseline.

    Args:
        disposition: a :class:`Disposition` value (or its string form).
        category: catalog category, used to look up manufacture-avoidance.
        item_weight_kg: shipped weight of the item.
        buyer_distance_km: distance to the P2P buyer (only used for P2P_LOCAL).

    Returns:
        kg CO2e avoided. ``RETURN_FC`` and any unknown disposition return 0.0
        because that path *is* the baseline (no avoidance).
    """
    # Normalise enum -> str so callers can pass either form.
    disp = disposition.value if isinstance(disposition, Disposition) else str(disposition)

    base = baseline_co2e(item_weight_kg)
    mfg = MANUFACTURE_AVOIDED.get(category, MANUFACTURE_AVOIDED["default"])

    if disp == Disposition.P2P_LOCAL.value:
        # Buyer nearby: near-zero transport + full manufacture avoidance.
        p2p_co2e = item_weight_kg * max(buyer_distance_km, 5.0) * EF_ROAD_KG_PER_KG_KM
        return base + mfg - p2p_co2e

    if disp == Disposition.DONATE_LOCAL.value:
        # Local NGO pickup: very short transport, partial manufacture credit.
        return base + (mfg * 0.7)

    if disp == Disposition.KEEP.value:
        # Customer keeps it: zero return transport, full manufacture avoidance.
        return base + mfg

    if disp == Disposition.REFURBISH.value:
        return base + (mfg * 0.85)

    if disp == Disposition.RESELL.value:
        return base + (mfg * 0.75)

    if disp == Disposition.RECYCLE.value:
        return base * 0.6  # transport to recycler still needed

    # RETURN_FC (baseline) or anything unrecognised — no avoidance.
    return 0.0


def coins_earned(co2e_kg: float, multiplier: int = COIN_MULTIPLIER) -> int:
    """Convert kg CO2e avoided into Green Coins (never negative)."""
    return max(0, int(co2e_kg * multiplier))


def equivalents(co2e_kg: float) -> dict[str, float]:
    """Convert raw kg CO2e into human-relatable equivalents for the UI."""
    return {
        "trees_per_month": round(co2e_kg / 0.83, 1),  # 1 tree ~ 0.83 kg CO2/month
        "km_not_driven": round(co2e_kg / 0.21, 1),    # avg car ~ 210 g CO2/km
        "phone_charges": round(co2e_kg / 0.008, 0),   # ~ 8 g CO2 per charge
    }
