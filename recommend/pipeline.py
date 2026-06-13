"""End-to-end wiring: user context + catalog -> ranked Feed.

This is the seam the service and tests call. It composes the pure pieces:
    profile -> embed -> retrieve -> rerank
Catalog item vectors should be precomputed once (see Recommender.__init__).
"""
from __future__ import annotations

from .embedder import embed_catalog, embed_text
from .profile import assemble_profile_text
from .rerank import rerank
from .retrieve import retrieve
from .schemas import Feed, HealthCard, UserContext


class Recommender:
    """Holds the precomputed catalog so per-request work is just embed+retrieve+rerank."""

    def __init__(
        self,
        sku_text: dict[str, str],
        cards: dict[str, HealthCard],
    ):
        """
        Args:
            sku_text: {sku_id: human-readable text (title + condition + ...)}.
            cards: {sku_id: HealthCard} for badging/boosting.
        """
        self.sku_text = sku_text
        self.cards = cards
        self.item_vecs = embed_catalog(sku_text)  # precompute once

    def recommend(self, user: UserContext, k: int | None = None) -> Feed:
        profile = assemble_profile_text(user, self.sku_text)
        user_vec = embed_text(profile)

        retrieved = retrieve(user_vec, self.item_vecs, k=None)

        # Reasons the matcher can attribute cheaply (wishlist hits).
        wishlist = set(user.wishlist)
        base_reasons = {
            sku_id: ["matches wishlist"] for sku_id, _ in retrieved if sku_id in wishlist
        }

        return rerank(user.user_id, retrieved, self.cards, base_reasons, k=k)
