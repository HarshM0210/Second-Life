"""The integration contracts, as code (per AGENTS.md).

These shapes are FROZEN. Changing them is a breaking change — announce to Gary
before merging. Parsers tolerate missing/extra fields so upstream teams can
evolve their payloads without breaking us.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# --- Input we consume: Health Card (from Module 1) ---------------------------
@dataclass
class HealthCard:
    sku_id: str
    condition: str = "Unknown"
    health_score: float = 0.0
    confidence: float = 0.0
    price: float = 0.0
    original_price: float = 0.0
    is_renewed: bool = False

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "HealthCard":
        """Tolerant parse — ignores extra fields, defaults missing ones."""
        return cls(
            sku_id=str(d["sku_id"]),
            condition=str(d.get("condition", "Unknown")),
            health_score=float(d.get("health_score", 0.0)),
            confidence=float(d.get("confidence", 0.0)),
            price=float(d.get("price", 0.0)),
            original_price=float(d.get("original_price", 0.0)),
            is_renewed=bool(d.get("is_renewed", False)),
        )

    @property
    def discount_frac(self) -> float:
        if self.original_price <= 0 or self.price <= 0:
            return 0.0
        return max(0.0, 1.0 - self.price / self.original_price)


# --- Input we consume: User context ------------------------------------------
@dataclass
class UserContext:
    user_id: str
    purchase_history: list[str] = field(default_factory=list)
    wishlist: list[str] = field(default_factory=list)
    searches: list[str] = field(default_factory=list)
    trends: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "UserContext":
        return cls(
            user_id=str(d["user_id"]),
            purchase_history=list(d.get("purchase_history", [])),
            wishlist=list(d.get("wishlist", [])),
            searches=list(d.get("searches", [])),
            trends=list(d.get("trends", [])),
        )


# --- Output we produce: Ranked feed (our public API) -------------------------
@dataclass
class FeedItem:
    sku_id: str
    rank: int
    score: float
    badge: str               # "New" | "Renewed"
    health_score: float
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sku_id": self.sku_id,
            "rank": self.rank,
            "score": round(self.score, 4),
            "badge": self.badge,
            "health_score": self.health_score,
            "reasons": self.reasons,
        }


@dataclass
class Feed:
    user_id: str
    items: list[FeedItem] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"user_id": self.user_id, "items": [i.to_dict() for i in self.items]}
