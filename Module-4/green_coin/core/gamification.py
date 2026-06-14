"""
green_coin/core/gamification.py

The behavioural-design layer: streak multipliers and impact milestone badges.

These are pure functions/data so they can be unit-tested without a DB. The
repositories supply the historical inputs (last earn time, prior streak,
cumulative CO2e) and persist the results.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


# ---------------------------------------------------------------------------
# Streaks
# ---------------------------------------------------------------------------


def apply_streak_multiplier(base_coins: int, current_streak: int) -> int:
    """Apply the consecutive-day eco-action multiplier.

    Day 7+ streak -> 1.5x, Day 3+ streak -> 1.2x, otherwise no bonus.
    """
    if current_streak >= 7:
        return int(base_coins * 1.5)
    if current_streak >= 3:
        return int(base_coins * 1.2)
    return base_coins


def compute_new_streak(
    last_earn_at: datetime | None,
    last_streak: int,
    now: datetime,
    reset_hours: int = 48,
) -> int:
    """Compute the streak day for a new earn event.

    Rules:
      * First-ever earn -> streak 1.
      * Gap larger than ``reset_hours`` -> streak resets to 1.
      * Same calendar day as the last earn -> streak unchanged.
      * Next day within the reset window -> streak increments.
    """
    if last_earn_at is None:
        return 1

    # Normalise to naive UTC comparison if tzinfo differs.
    if last_earn_at.tzinfo is not None and now.tzinfo is None:
        last_earn_at = last_earn_at.replace(tzinfo=None)
    elif last_earn_at.tzinfo is None and now.tzinfo is not None:
        now = now.replace(tzinfo=None)

    if now - last_earn_at > timedelta(hours=reset_hours):
        return 1

    if now.date() == last_earn_at.date():
        return max(1, last_streak)

    return max(1, last_streak) + 1


# ---------------------------------------------------------------------------
# Badges
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Badge:
    """An impact milestone badge awarded at a cumulative CO2e threshold."""

    slug: str
    name: str
    icon: str
    threshold_kg: float
    equivalent: str


# Ordered ascending by threshold.
BADGES: tuple[Badge, ...] = (
    Badge("seed_saver", "Seed Saver", "🌱", 5.0, "6 trees planted"),
    Badge("green_guardian", "Green Guardian", "🌿", 25.0, "Skipped 119 km of driving"),
    Badge("forest_keeper", "Forest Keeper", "🌳", 100.0, "Powered a home for 2 weeks"),
    Badge("planet_protector", "Planet Protector", "🌍", 500.0, "Offset a flight Mumbai→Delhi"),
)

_BADGE_BY_SLUG: dict[str, Badge] = {b.slug: b for b in BADGES}


def badge_for_slug(slug: str | None) -> Badge | None:
    """Look up a badge by its slug (``None`` -> ``None``)."""
    if slug is None:
        return None
    return _BADGE_BY_SLUG.get(slug)


def newly_earned_badge(previous_total_kg: float, new_total_kg: float) -> Badge | None:
    """Return the highest badge whose threshold was crossed by this earn event.

    A badge is "crossed" when the cumulative CO2e moves from below its
    threshold to at or above it. If several thresholds are crossed at once
    (a large single event), the highest is returned so the UI celebrates the
    most impressive milestone.
    """
    crossed = [
        b for b in BADGES
        if previous_total_kg < b.threshold_kg <= new_total_kg
    ]
    if not crossed:
        return None
    return max(crossed, key=lambda b: b.threshold_kg)


def unlocked_badges(total_kg: float) -> list[Badge]:
    """All badges unlocked at the given cumulative CO2e total."""
    return [b for b in BADGES if total_kg >= b.threshold_kg]
