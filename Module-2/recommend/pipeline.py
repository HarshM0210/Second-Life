"""End-to-end wiring: user context + catalog -> ranked Feed.

Composes: profile -> embed -> retrieve -> [cross-encoder rerank] -> business rerank
Catalog item vectors precomputed once at init.
"""
from __future__ import annotations

from .embedder import embed_catalog, embed_text
from .profile import assemble_profile_text
from .rerank import rerank
from .retrieve import cosine_similarity, retrieve
from .schemas import Feed, HealthCard, UserContext


class Recommender:
    """Holds the precomputed catalog so per-request work is just embed+retrieve+rerank."""

    def __init__(self, sku_text: dict[str, str], cards: dict[str, HealthCard],
                 use_cross_encoder: bool = False):
        self.sku_text = sku_text
        self.cards = cards
        self.item_vecs = embed_catalog(sku_text)  # precompute once
        self.use_cross_encoder = use_cross_encoder

    def _build_reasons(self, user: UserContext, retrieved: list[tuple[str, float]]) -> dict[str, list[str]]:
        """Generate per-item reason strings from user context signals."""
        reasons: dict[str, list[str]] = {}
        wishlist_set = set(user.wishlist)
        history_set = set(user.purchase_history)

        # Precompute history vectors for "similar to past purchase" detection
        hist_vecs = [self.item_vecs[s] for s in history_set if s in self.item_vecs]

        for sku_id, _ in retrieved:
            r: list[str] = []
            if sku_id in wishlist_set:
                r.append("matches wishlist")
            if sku_id in history_set:
                r.append("previously purchased")
            elif hist_vecs and sku_id in self.item_vecs:
                max_sim = max(cosine_similarity(self.item_vecs[sku_id], hv) for hv in hist_vecs)
                if max_sim > 0.7:
                    r.append("similar to past purchase")
            # Trending match
            if user.trends:
                text = self.sku_text.get(sku_id, "").lower()
                for trend in user.trends:
                    if trend.lower() in text:
                        r.append(f"trending in {trend}")
                        break
            if r:
                reasons[sku_id] = r
        return reasons

    def recommend(self, user: UserContext, k: int | None = None) -> Feed:
        profile = assemble_profile_text(user, self.sku_text, self.cards)
        user_vec = embed_text(profile)
        retrieved = retrieve(user_vec, self.item_vecs, k=None)

        # Optional two-stage: cross-encoder re-scores top candidates
        if self.use_cross_encoder and retrieved:
            from .cross_encoder import cross_encoder_rerank
            retrieved = cross_encoder_rerank(
                query=profile, candidates=retrieved,
                texts=self.sku_text, top_n=min(20, len(retrieved)),
            )

        base_reasons = self._build_reasons(user, retrieved)
        return rerank(user.user_id, retrieved, self.cards, base_reasons, k=k)
