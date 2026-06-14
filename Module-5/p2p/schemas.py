"""Frozen integration contracts as dataclasses with tolerant from_dict parsers."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict, fields
from typing import List, Optional


def _safe_float(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _safe_int(v, default=0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _pick(cls, d: dict) -> dict:
    """Pick only keys that match dataclass fields, ignoring extras."""
    names = {f.name for f in fields(cls)}
    return {k: v for k, v in d.items() if k in names}


@dataclass
class HealthCard:
    sku_id: str = ""
    condition: str = "Unknown"
    health_score: float = 0.0
    confidence: float = 0.0
    price: float = 0.0
    original_price: float = 0.0
    is_renewed: bool = False

    @classmethod
    def from_dict(cls, d: dict) -> HealthCard:
        if not d:
            return cls()
        return cls(
            sku_id=str(d.get("sku_id", "")),
            condition=str(d.get("condition", "Unknown")),
            health_score=_safe_float(d.get("health_score")),
            confidence=_safe_float(d.get("confidence")),
            price=_safe_float(d.get("price")),
            original_price=_safe_float(d.get("original_price")),
            is_renewed=bool(d.get("is_renewed", False)),
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ItemListing:
    sku_id: str = ""
    category: str = "general"
    original_price: float = 0.0
    age_months: int = 0
    brand_tier: str = "standard"
    has_box: bool = True
    accessories_complete: bool = True
    media_refs: List[str] = field(default_factory=list)
    health_card: Optional[HealthCard] = None

    @classmethod
    def from_dict(cls, d: dict) -> ItemListing:
        if not d:
            return cls()
        hc = d.get("health_card")
        return cls(
            sku_id=str(d.get("sku_id", "")),
            category=str(d.get("category", "general")),
            original_price=_safe_float(d.get("original_price")),
            age_months=_safe_int(d.get("age_months")),
            brand_tier=str(d.get("brand_tier", "standard")),
            has_box=bool(d.get("has_box", True)),
            accessories_complete=bool(d.get("accessories_complete", True)),
            media_refs=list(d.get("media_refs", [])),
            health_card=HealthCard.from_dict(hc) if hc else None,
        )

    def to_dict(self) -> dict:
        out = asdict(self)
        if self.health_card is None:
            out.pop("health_card", None)
        return out


@dataclass
class FeatureVector:
    condition_score: float = 50.0
    original_price: float = 0.0
    age_months: int = 0
    category_demand: float = 0.5
    category_depreciation: float = 0.5
    brand_multiplier: float = 1.0
    completeness: float = 1.0
    source: str = "direct"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PriceQuote:
    sku_id: str = ""
    gross_price: float = 0.0
    low: float = 0.0
    high: float = 0.0
    confidence: float = 0.0
    fee: float = 0.0
    net_payout: float = 0.0
    currency: str = "INR"
    feature_source: str = "direct"
    model: str = ""                       # "neural-quantile-mlp" | "heuristic-fallback"
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PickupJob:
    job_id: str = ""
    sku_id: str = ""
    status: str = "scheduled"
    pickup_eta: str = ""
    agent: str = ""
    created_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)
