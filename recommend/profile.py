"""User profile assembler: user context -> a single text blob to embed.

Per README Module 2: "history + wishlist + searches -> text blob", plus trends.
Kept deliberately simple and pure so it's easy to test and tune.

Maddie: if you enrich SKUs to titles/categories (recommended — raw sku_ids
don't embed meaningfully with a real text model), resolve them here via the
catalog and weight wishlist/searches higher than old history.
"""
from __future__ import annotations

from .schemas import UserContext


def assemble_profile_text(
    user: UserContext,
    sku_text: dict[str, str] | None = None,
) -> str:
    """Flatten a user's signals into one text blob.

    Args:
        user: the user context.
        sku_text: optional {sku_id: human-readable text} to resolve history/
            wishlist SKUs into meaningful tokens. If absent, raw ids are used.
    """
    def resolve(ids: list[str]) -> list[str]:
        if not sku_text:
            return list(ids)
        return [sku_text.get(i, i) for i in ids]

    parts: list[str] = []
    # Weight intent signals (wishlist, searches) higher by repeating them.
    parts += resolve(user.wishlist) * 2
    parts += user.searches * 2
    parts += resolve(user.purchase_history)
    parts += user.trends
    return " ".join(p for p in parts if p)
