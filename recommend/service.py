"""FastAPI surface for Module 2 — one endpoint: GET /recommend?user_id=

Slots into the shared backend service per README. Loads fixtures at startup as
the demo catalog; swap for the real catalog/Health-Card source when upstream
(Module 1) is wired in.

Run locally:  uvicorn recommend.service:app --reload
"""
from __future__ import annotations

import json
from pathlib import Path

try:
    from fastapi import FastAPI, HTTPException
except ImportError:  # FastAPI is optional for unit tests; the pipeline works without it.
    FastAPI = None  # type: ignore

from .pipeline import Recommender
from .schemas import HealthCard, UserContext

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def load_recommender(fixtures_dir: Path = FIXTURES) -> Recommender:
    catalog = json.loads((fixtures_dir / "catalog.json").read_text())
    cards_raw = json.loads((fixtures_dir / "health_cards.json").read_text())
    sku_text = {item["sku_id"]: item["text"] for item in catalog}
    cards = {c["sku_id"]: HealthCard.from_dict(c) for c in cards_raw}
    return Recommender(sku_text, cards)


def load_users(fixtures_dir: Path = FIXTURES) -> dict[str, UserContext]:
    users_raw = json.loads((fixtures_dir / "users.json").read_text())
    return {u["user_id"]: UserContext.from_dict(u) for u in users_raw}


if FastAPI is not None:
    app = FastAPI(title="Second Life — Recommend (Module 2)")
    _recommender = load_recommender()
    _users = load_users()

    @app.get("/recommend")
    def recommend(user_id: str, k: int = 10):
        user = _users.get(user_id)
        if user is None:
            raise HTTPException(status_code=404, detail=f"unknown user_id: {user_id}")
        return _recommender.recommend(user, k=k).to_dict()

    @app.get("/health")
    def health():
        return {"status": "ok", "module": "recommend"}
