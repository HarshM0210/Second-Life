"""
return_prevention/taxonomy/taxonomy_loader.py

Loads the Category_Taxonomy from a local JSON or CSV file into an in-memory
dictionary keyed by subcategory name. The taxonomy is loaded once at startup
and accessed via the module-level `get_taxonomy()` singleton getter.

Requirements: 3.4, 3.5, 3.6, 3.7
"""

from __future__ import annotations

import csv
import json
import logging
import os
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TaxonomyEntry:
    """A single subcategory entry in the Category Taxonomy."""

    category: str
    subcategory: str
    category_return_rate: float
    has_size_ambiguity: bool


# ---------------------------------------------------------------------------
# Module-level singleton state
# ---------------------------------------------------------------------------

_taxonomy: Optional[dict[str, TaxonomyEntry]] = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_taxonomy(path: str) -> dict[str, TaxonomyEntry]:
    """
    Read a taxonomy file (JSON or CSV) and return a dict keyed by subcategory name.

    The file format is determined by the file extension:
      - `.json`: expects a JSON array of objects with keys
        `category`, `subcategory`, `category_return_rate`, `has_size_ambiguity`
      - `.csv`: expects a CSV with headers matching the same keys

    Raises:
        RuntimeError: If the file is missing or cannot be parsed.
    """
    global _taxonomy

    if not os.path.isfile(path):
        raise RuntimeError(
            f"Taxonomy file not found: '{path}'. "
            f"The service cannot start without a valid taxonomy file."
        )

    ext = os.path.splitext(path)[1].lower()

    try:
        if ext == ".json":
            entries = _load_json(path)
        elif ext == ".csv":
            entries = _load_csv(path)
        else:
            raise RuntimeError(
                f"Unsupported taxonomy file format '{ext}' for path: '{path}'. "
                f"Only .json and .csv are supported."
            )
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(
            f"Failed to parse taxonomy file '{path}': {exc}"
        ) from exc

    _taxonomy = entries
    logger.info(
        "taxonomy_loaded entries=%d path=%s",
        len(_taxonomy),
        path,
    )
    return _taxonomy


def get_taxonomy() -> Optional[dict[str, TaxonomyEntry]]:
    """
    Return the already-loaded taxonomy dict, or None if not yet loaded.

    This is the singleton getter used by other modules after startup.
    """
    return _taxonomy


# ---------------------------------------------------------------------------
# Internal loaders
# ---------------------------------------------------------------------------


def _load_json(path: str) -> dict[str, TaxonomyEntry]:
    """Parse a JSON taxonomy file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Malformed JSON in taxonomy file '{path}': {exc}"
        ) from exc

    if not isinstance(raw, list):
        raise RuntimeError(
            f"Taxonomy JSON file '{path}' must contain a top-level array, "
            f"got {type(raw).__name__}."
        )

    return _parse_entries(raw, path)


def _load_csv(path: str) -> dict[str, TaxonomyEntry]:
    """Parse a CSV taxonomy file."""
    try:
        with open(path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except Exception as exc:
        raise RuntimeError(
            f"Failed to read CSV taxonomy file '{path}': {exc}"
        ) from exc

    if not rows:
        raise RuntimeError(
            f"Taxonomy CSV file '{path}' is empty or has no data rows."
        )

    return _parse_entries(rows, path)


def _parse_entries(
    raw_entries: list[dict],
    path: str,
) -> dict[str, TaxonomyEntry]:
    """
    Validate and convert raw dicts into TaxonomyEntry objects keyed by subcategory.
    """
    taxonomy: dict[str, TaxonomyEntry] = {}
    required_keys = {"category", "subcategory", "category_return_rate", "has_size_ambiguity"}

    for i, entry in enumerate(raw_entries):
        if not isinstance(entry, dict):
            raise RuntimeError(
                f"Taxonomy entry at index {i} in '{path}' is not a dict/object."
            )

        missing = required_keys - set(entry.keys())
        if missing:
            raise RuntimeError(
                f"Taxonomy entry at index {i} in '{path}' is missing keys: "
                f"{sorted(missing)}"
            )

        try:
            category = str(entry["category"])
            subcategory = str(entry["subcategory"])
            category_return_rate = float(entry["category_return_rate"])
            has_size_ambiguity = _parse_bool(entry["has_size_ambiguity"])
        except (TypeError, ValueError) as exc:
            raise RuntimeError(
                f"Invalid data in taxonomy entry at index {i} in '{path}': {exc}"
            ) from exc

        taxonomy[subcategory] = TaxonomyEntry(
            category=category,
            subcategory=subcategory,
            category_return_rate=category_return_rate,
            has_size_ambiguity=has_size_ambiguity,
        )

    return taxonomy


def _parse_bool(value: object) -> bool:
    """Parse a boolean from JSON bool or CSV string representation."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lower = value.strip().lower()
        if lower in ("true", "1", "yes"):
            return True
        if lower in ("false", "0", "no"):
            return False
    raise ValueError(f"Cannot interpret {value!r} as a boolean")
