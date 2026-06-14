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
        def safe_float(v, default=0.0):
            try:
                return float(v)
            except (ValueError, TypeError):
                return default

        return cls(
            sku_id=str(d.get("sku_id", "unknown")),
            condition=str(d.get("condition", "Unknown")),
            health_score=safe_float(d.get("health_score")),
            confidence=safe_float(d.get("confidence")),
            price=safe_float(d.get("price")),
            original_price=safe_float(d.get("original_price")),
            is_renewed=bool(d.get("is_renewed", False)),
        )

    @property
    def discount_frac(self) -> float:
        if self.original_price <= 0 or self.price <= 0:
            return 0.0
        return max(0.0, 1.0 - self.price / self.original_price)


# --- Input we consume: Social profile (consent-gated) ------------------------
@dataclass
class SocialProfile:
    """Signals from a user's connected social account. USED ONLY IF consent=True.

    Privacy: this is opt-in. A mock connector populates it from fixtures for the
    demo; real OAuth integrations + data-minimization are the production path.
    """
    consent: bool = False
    follows: list[str] = field(default_factory=list)   # brands / creators followed
    likes: list[str] = field(default_factory=list)     # liked posts / products
    topics: list[str] = field(default_factory=list)     # hashtags / topics engaged
    captions: list[str] = field(default_factory=list)   # user's own posts / bio text

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> "SocialProfile":
        if not d:
            return cls()
        return cls(
            consent=bool(d.get("consent", False)),
            follows=list(d.get("follows", [])),
            likes=list(d.get("likes", [])),
            topics=list(d.get("topics", [])),
            captions=list(d.get("captions", [])),
        )

    @property
    def active(self) -> bool:
        """True only when the user consented AND there is some signal to use."""
        return self.consent and bool(self.follows or self.likes or self.topics or self.captions)


# --- Input we consume: User context ------------------------------------------
@dataclass
class UserContext:
    user_id: str
    purchase_history: list[str] = field(default_factory=list)
    wishlist: list[str] = field(default_factory=list)
    searches: list[str] = field(default_factory=list)
    trends: list[str] = field(default_factory=list)
    social: SocialProfile = field(default_factory=SocialProfile)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "UserContext":
        return cls(
            user_id=str(d["user_id"]),
            purchase_history=list(d.get("purchase_history", [])),
            wishlist=list(d.get("wishlist", [])),
            searches=list(d.get("searches", [])),
            trends=list(d.get("trends", [])),
            social=SocialProfile.from_dict(d.get("social")),
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
