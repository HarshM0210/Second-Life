"""User profile assembler: user context -> a single text blob to embed.

Resolves SKU IDs to meaningful text (title + condition + price context) so
real embeddings capture intent, not opaque identifiers.
"""
from __future__ import annotations

from .schemas import HealthCard, UserContext


def _enrich_sku(sku_id: str, sku_text: dict[str, str], cards: dict[str, HealthCard] | None) -> str:
    """Resolve a SKU to rich text: title + condition/price if available."""
    base = sku_text.get(sku_id, sku_id)
    if cards and sku_id in cards:
        c = cards[sku_id]
        if c.is_renewed and c.discount_frac > 0:
            base += f" {c.condition} condition {c.discount_frac*100:.0f}% off"
    return base


def assemble_profile_text(
    user: UserContext,
    sku_text: dict[str, str] | None = None,
    cards: dict[str, HealthCard] | None = None,
) -> str:
    """Flatten a user's signals into one text blob for embedding.

    Weighting: wishlist/searches repeated 2x (higher intent signal than history).
    """
    def resolve(ids: list[str]) -> list[str]:
        if not sku_text:
            return list(ids)
        return [_enrich_sku(i, sku_text, cards) for i in ids]

    parts: list[str] = []
    parts += resolve(user.wishlist) * 2
    parts += user.searches * 2
    parts += resolve(user.purchase_history)
    parts += user.trends
    return " ".join(p for p in parts if p)
