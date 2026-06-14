"""
green_coin/core/rewards.py

Loads and caches the redeemable rewards catalog from a JSON file.

By design (see README §4) coins are only redeemable on sustainability-positive
actions — overwhelmingly Renewed inventory — so that every redemption drives one
more circular transaction rather than subsidising new manufacture.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from green_coin.schemas.coins import Reward

logger = logging.getLogger(__name__)

_catalog: dict[str, Reward] | None = None


def load_rewards(path: str) -> dict[str, Reward]:
    """Load the rewards catalog from ``path`` and cache it as a singleton.

    Raises:
        RuntimeError: if the file is missing or malformed — the service should
            refuse to start without a valid catalog.
    """
    global _catalog
    file_path = Path(path)
    try:
        raw = json.loads(file_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"rewards catalog not found at {path!r}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"rewards catalog at {path!r} is not valid JSON: {exc}") from exc

    try:
        rewards = [Reward(**item) for item in raw]
    except Exception as exc:  # pydantic validation / shape errors
        raise RuntimeError(f"rewards catalog at {path!r} has invalid entries: {exc}") from exc

    _catalog = {r.reward_id: r for r in rewards}
    logger.info("rewards_loaded count=%d path=%s", len(_catalog), path)
    return _catalog


def get_rewards() -> dict[str, Reward]:
    """Return the cached catalog, raising if it has not been loaded yet."""
    if _catalog is None:
        raise RuntimeError("rewards catalog accessed before load_rewards() was called")
    return _catalog


def get_reward(reward_id: str) -> Reward | None:
    """Look up a single reward by id (``None`` if unknown)."""
    return get_rewards().get(reward_id)
