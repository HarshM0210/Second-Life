"""All tunable knobs live here — one block, not scattered (per AGENTS.md).

Maddie: tune these against the demo cases. Ross: tests should not hard-code
values that duplicate these; import from here.
"""
from dataclasses import dataclass, field
import os


@dataclass(frozen=True)
class RerankConfig:
    # Final score = similarity + renewed_boost(item). See rerank.py.
    # Boost applied to Renewed items, scaled by how far health_score exceeds the floor.
    renewed_boost_weight: float = 0.18   # max additive boost for a perfect Renewed item
    health_score_floor: float = 70.0     # below this, no boost
    health_score_ceil: float = 100.0     # boost saturates here
    discount_boost_weight: float = 0.04  # extra nudge for a genuine price cut vs original
    min_confidence: float = 0.30         # Health Cards below this confidence get no boost


@dataclass(frozen=True)
class EmbedConfig:
    # Env-overridable so constrained hosts can swap the 768-dim gte-modernbert
    # (~600 MB) for the lighter 384-dim bge-small (~130 MB) with no code change:
    #   RECOMMEND_TEXT_MODEL=BAAI/bge-small-en-v1.5  RECOMMEND_EMBED_DIM=384
    text_model: str = field(
        default_factory=lambda: os.environ.get(
            "RECOMMEND_TEXT_MODEL", "Alibaba-NLP/gte-modernbert-base"
        )
    )                                                    # 2025 model; local, no API
    image_model: str = "ViT-B/32"                        # CLIP, optional
    dim: int = field(
        default_factory=lambda: int(os.environ.get("RECOMMEND_EMBED_DIM", "768"))
    )                                                    # must match text_model


@dataclass(frozen=True)
class SocialConfig:
    """Consent-gated social signals → profile text. Weights are repeat-counts
    (same mechanism as profile.py's 2× wishlist), so stronger signals dominate the
    embedded profile. Follows/likes are explicit affinity; captions are noisiest."""
    follows_weight: int = 2   # brands/creators followed — strongest, low-noise
    likes_weight: int = 2     # liked posts/products — recent intent
    topics_weight: int = 1    # hashtags/topics — broad interest
    captions_weight: int = 1  # own posts/bio — richest but noisiest


RERANK = RerankConfig()
EMBED = EmbedConfig()
SOCIAL = SocialConfig()
