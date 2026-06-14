"""Unit tests for streak multipliers and badge milestones."""

from __future__ import annotations

from datetime import datetime, timedelta

from green_coin.core.gamification import (
    apply_streak_multiplier,
    compute_new_streak,
    newly_earned_badge,
    unlocked_badges,
)


def test_streak_multiplier_tiers():
    assert apply_streak_multiplier(100, 1) == 100
    assert apply_streak_multiplier(100, 3) == 120
    assert apply_streak_multiplier(100, 7) == 150


def test_first_earn_starts_streak_at_one():
    assert compute_new_streak(None, 0, datetime(2026, 6, 14, 12, 0)) == 1


def test_same_day_keeps_streak():
    last = datetime(2026, 6, 14, 9, 0)
    now = datetime(2026, 6, 14, 20, 0)
    assert compute_new_streak(last, 4, now) == 4


def test_next_day_increments_streak():
    last = datetime(2026, 6, 14, 20, 0)
    now = datetime(2026, 6, 15, 9, 0)
    assert compute_new_streak(last, 4, now) == 5


def test_gap_over_window_resets_streak():
    last = datetime(2026, 6, 10, 9, 0)
    now = datetime(2026, 6, 14, 9, 0)  # 4 days later
    assert compute_new_streak(last, 9, now, reset_hours=48) == 1


def test_badge_crossing_threshold():
    badge = newly_earned_badge(previous_total_kg=3.0, new_total_kg=6.0)
    assert badge is not None and badge.slug == "seed_saver"


def test_no_badge_when_threshold_not_crossed():
    assert newly_earned_badge(6.0, 7.0) is None


def test_highest_badge_when_multiple_crossed():
    badge = newly_earned_badge(previous_total_kg=0.0, new_total_kg=120.0)
    assert badge is not None and badge.slug == "forest_keeper"


def test_unlocked_badges_cumulative():
    slugs = {b.slug for b in unlocked_badges(30.0)}
    assert slugs == {"seed_saver", "green_guardian"}
