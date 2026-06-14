"""FastAPI surface for Module 2 — one endpoint: GET /recommend?user_id=

Loads catalog and Health Cards from a configurable source (env vars) with
fixture fallback for offline/demo mode.

Run locally:  uvicorn recommend.service:app --reload
"""
from __future__ import annotations

import json
import os
from pathlib import Path

try:
    from fastapi import FastAPI, HTTPException
except ImportError:
    FastAPI = None  # type: ignore

from .pipeline import Recommender
from .schemas import HealthCard, UserContext
from .embedder import validate_embedder, is_model_loaded

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def _load_json(env_key: str, fixture_name: str) -> list[dict]:
    """Load from env-specified path if set, else fall back to fixtures."""
    path = os.environ.get(env_key)
    if path and Path(path).exists():
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return json.loads((FIXTURES / fixture_name).read_text(encoding="utf-8"))


def load_recommender() -> Recommender:
    """Load data and validate that the ML model is operational."""
    # R8: Ensure the real model is available and producing dense vectors.
    # This prevents silent fallback to low-quality hash vectors during the demo.
    validate_embedder()

    catalog = _load_json("RECOMMEND_CATALOG", "catalog.json")
    cards_raw = _load_json("RECOMMEND_HEALTH_CARDS", "health_cards.json")
    sku_text = {item["sku_id"]: item["text"] for item in catalog}
    cards = {c["sku_id"]: HealthCard.from_dict(c) for c in cards_raw}
    return Recommender(sku_text, cards)


def load_users() -> dict[str, UserContext]:
    users_raw = _load_json("RECOMMEND_USERS", "users.json")
    return {u["user_id"]: UserContext.from_dict(u) for u in users_raw}


def load_customer_profiles() -> dict[str, dict]:
    """Load the Customer_Profile store consumed by Module 3 (Return Prevention).

    Keyed by customer_id; each value carries an ``order_history`` list. Module 3
    reads ``order_history[].subcategory`` and ``.status`` to compute the
    per-user category return rate.
    """
    profiles_raw = _load_json("RECOMMEND_CUSTOMER_PROFILES", "customer_profiles.json")
    return {p["customer_id"]: p for p in profiles_raw}


_recommender: "Recommender | None" = None
_users: "dict[str, UserContext] | None" = None
_customer_profiles: "dict[str, dict] | None" = None


if FastAPI is not None:
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def lifespan(app):
        global _recommender, _users, _customer_profiles
        _recommender = load_recommender()
        _users = load_users()
        _customer_profiles = load_customer_profiles()
        yield

    app = FastAPI(title="Second Life — Recommend (Module 2)", lifespan=lifespan)

    @app.get("/recommend")
    def recommend(user_id: str, k: int = 10):
        user = _users.get(user_id)
        if user is None:
            raise HTTPException(status_code=404, detail=f"unknown user_id: {user_id}")
        return _recommender.recommend(user, k=k).to_dict()

    @app.get("/api/v2/customer-profile/{customer_id}")
    def customer_profile(customer_id: str):
        """Customer_Profile store consumed by Module 3 (read-only).

        Returns 200 with the stored ``order_history`` for known customers, or a
        valid empty profile for unknown ones (never 404) so Module 3's client —
        which only catches transport errors — degrades to category baselines
        instead of raising.
        """
        profile = (_customer_profiles or {}).get(customer_id)
        if profile is None:
            return {"customer_id": customer_id, "order_history": []}
        return profile

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "module": "recommend",
            "model_loaded": is_model_loaded()
        }
