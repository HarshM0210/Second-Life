"""Cross-module value mappings.

Each module speaks its own vocabulary. These pure functions translate between
them so the orchestrator can route a Health Card from Module 1 into Module 4's
CO2e engine and Module 5's pricing model without leaking module-specific enums
across boundaries.
"""
from __future__ import annotations

# Module 1 disposition  ->  Module 4 Disposition enum
# Module 4 enum: P2P_LOCAL | DONATE_LOCAL | KEEP | REFURBISH | RESELL | RECYCLE | RETURN_FC
_DISPOSITION_M1_TO_M4 = {
    "resell": "RESELL",
    "refurbish": "REFURBISH",
    "donate": "DONATE_LOCAL",
    "recycle": "RECYCLE",
    "return_to_seller": "RETURN_FC",
    "manual_review": "RETURN_FC",
}

# Module 1 category  ->  Module 4 MANUFACTURE_AVOIDED key
_CATEGORY_M1_TO_M4 = {
    "Electronics": "electronics",
    "Clothing & Footwear": "clothing",
    "Food & Grocery": "default",
    "Other": "default",
}

# Module 1 category  ->  Module 5 category enum
_CATEGORY_M1_TO_M5 = {
    "Electronics": "electronics",
    "Clothing & Footwear": "fashion",
    "Food & Grocery": "kitchen",
    "Other": "electronics",
}


def disposition_to_green_coin(disposition: str, chose_p2p: bool = False) -> str:
    """Translate a Health Card disposition into a Green Coin disposition.

    A customer who diverted to P2P always earns the top-tier ``P2P_LOCAL``
    reward regardless of the grading disposition.
    """
    if chose_p2p:
        return "P2P_LOCAL"
    return _DISPOSITION_M1_TO_M4.get(disposition, "RETURN_FC")


def category_to_green_coin(category: str) -> str:
    return _CATEGORY_M1_TO_M4.get(category, "default")


def category_to_p2p(category: str) -> str:
    return _CATEGORY_M1_TO_M5.get(category, "electronics")


def brand_tier_for(health_score: float) -> str:
    """Coarse brand-tier guess for the P2P listing from item quality."""
    if health_score >= 90:
        return "premium"
    if health_score >= 70:
        return "standard"
    return "value"
