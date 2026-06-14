"""Dual-path feature extraction orchestrator."""
from p2p.schemas import ItemListing, FeatureVector
from p2p.config import CONFIG
from p2p import media


def extract_features(listing: ItemListing) -> FeatureVector:
    """Extract features via health_card path or direct (CLIP) path."""
    if listing.health_card and listing.health_card.health_score > 0:
        condition_score = listing.health_card.health_score
        source = "health_card"
    else:
        condition_score = media.score_condition(listing.media_refs)
        source = "direct"

    cat = CONFIG.category_tables.get(listing.category)
    return FeatureVector(
        condition_score=condition_score,
        original_price=listing.original_price,
        age_months=listing.age_months,
        category_demand=cat[2] if cat else 0.5,
        category_depreciation=cat[1] if cat else 0.05,
        brand_multiplier=CONFIG.brand_multipliers.get(listing.brand_tier, 1.0),
        completeness=(0.5 if listing.has_box else 0) + (0.5 if listing.accessories_complete else 0),
        source=source,
    )
