"""All tunable knobs live here — one block, not scattered (per AGENTS.md).

Maddie: tune these against the demo cases. Ross: tests should not hard-code
values that duplicate these; import from here.
"""
from dataclasses import dataclass


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
    text_model: str = "BAAI/bge-small-en-v1.5"  # local; downloaded once, no API
    image_model: str = "ViT-B/32"               # CLIP, optional
    dim: int = 384                              # bge-small-en-v1.5 dimension


RERANK = RerankConfig()
EMBED = EmbedConfig()
