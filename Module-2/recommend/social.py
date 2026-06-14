"""Social Media access — consent-gated social signals for recommendation.

A user's connected social activity (follows, likes, topics, post/bio text) becomes
another *interest-text* signal that feeds `profile.assemble_profile_text` → embeddings
→ ranking, exactly like wishlist/searches. Nothing is used unless the user consented.

Demo: `connect()` is a MOCK connector returning fixture-backed signals. Real OAuth
connectors (Instagram/X/…) + data-minimization/retention controls are the production
path — see documentation.md. No scraping, no credentials here.
"""
from __future__ import annotations

from .config import SOCIAL
from .schemas import SocialProfile, UserContext


def connect(user_id: str, raw: dict | None, *, consent: bool) -> SocialProfile:
    """Mock connector: turn a raw 'connected account' payload into a SocialProfile.

    Consent is explicit and authoritative — without it we return an empty (inactive)
    profile regardless of what `raw` contains.
    """
    if not consent or not raw:
        return SocialProfile(consent=False)
    profile = SocialProfile.from_dict(raw)
    profile.consent = consent
    return profile


def extract_social_text(user: UserContext) -> str:
    """Weighted interest text from social signals — '' unless the user consented."""
    s = user.social
    if not s.active:
        return ""
    parts: list[str] = []
    parts += s.follows * SOCIAL.follows_weight
    parts += s.likes * SOCIAL.likes_weight
    parts += s.topics * SOCIAL.topics_weight
    parts += s.captions * SOCIAL.captions_weight
    return " ".join(p for p in parts if p)


def social_interest_terms(user: UserContext) -> set[str]:
    """Lowercased tokens from social signals, for per-item reason matching.

    Empty without consent. Short tokens (≤2 chars) dropped to avoid noise matches.
    """
    s = user.social
    if not s.active:
        return set()
    terms: set[str] = set()
    for signal in (s.follows, s.likes, s.topics, s.captions):
        for item in signal:
            terms.update(tok for tok in item.lower().split() if len(tok) > 2)
    return terms
