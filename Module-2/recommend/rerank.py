"""Re-ranking — where the recommendation business rules live (NOT in retrieve.py).

The novel bit of Module 2: inject Renewed inventory into the same ranking and
boost high-Health-Score Renewed items so resale supply clears. All weights come
from config.RERANK — keep them there, not inline.
"""
from __future__ import annotations

from .config import RERANK
from .schemas import Feed, FeedItem, HealthCard


def _renewed_boost(card: HealthCard) -> tuple[float, list[str]]:
    """Additive boost + human-readable reasons for a Renewed item.

    Returns (0.0, []) for new items, low-confidence cards, or scores below the
    floor (we wouldn't resell those anyway).
    """
    if not card.is_renewed:
        return 0.0, []
    if card.confidence < RERANK.min_confidence:
        return 0.0, []
    if card.health_score < RERANK.health_score_floor:
        return 0.0, []

    span = RERANK.health_score_ceil - RERANK.health_score_floor
    frac = (card.health_score - RERANK.health_score_floor) / span if span > 0 else 0.0
    frac = max(0.0, min(1.0, frac))

    boost = RERANK.renewed_boost_weight * frac
    reasons = [f"Renewed, health {card.health_score:.0f}"]

    if card.discount_frac > 0:
        boost += RERANK.discount_boost_weight * card.discount_frac
        reasons.append(f"{card.discount_frac * 100:.0f}% off original")

    return boost, reasons


def rerank(
    user_id: str,
    retrieved: list[tuple[str, float]],
    cards: dict[str, HealthCard],
    base_reasons: dict[str, list[str]] | None = None,
    k: int | None = None,
    market_state: "MarketState | None" = None,
) -> Feed:
    """Apply Renewed/Health-Score boosting + market-aware policy on top of retrieval.

    Args:
        user_id: who this feed is for.
        retrieved: [(sku_id, similarity)] from retrieve().
        cards: {sku_id: HealthCard} for badge/boost. Missing card => treated New.
        base_reasons: optional {sku_id: [reason]} from the matcher.
        k: optional cap on feed length.
        market_state: optional MarketState for policy adjustment.

    Returns:
        Feed with items sorted by final score desc, sku_id asc for ties.
    """
    from .policy import MarketState, policy_adjustment

    base_reasons = base_reasons or {}
    if market_state is None:
        market_state = MarketState()
    items: list[FeedItem] = []

    for sku_id, sim in retrieved:
        card = cards.get(sku_id)
        boost, boost_reasons = _renewed_boost(card) if card else (0.0, [])
        is_renewed = card.is_renewed if card else False
        pol_adj, pol_reasons = policy_adjustment(market_state, is_renewed)
        reasons = list(base_reasons.get(sku_id, [])) + boost_reasons + pol_reasons
        items.append(
            FeedItem(
                sku_id=sku_id,
                rank=0,
                score=sim + boost + pol_adj,
                badge="Renewed" if is_renewed else "New",
                health_score=card.health_score if card else 0.0,
                reasons=reasons,
            )
        )

    items.sort(key=lambda it: (-it.score, it.sku_id))
    if k is not None:
        items = items[:k]
    for i, it in enumerate(items, start=1):
        it.rank = i

    return Feed(user_id=user_id, items=items)
