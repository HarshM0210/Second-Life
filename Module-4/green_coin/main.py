"""
green_coin/main.py

FastAPI application factory for Module 4 — Sustainability Credits ("Green Coin").

Startup sequence:
  1. Create DB tables (event-sourced ledger)
  2. Load the rewards catalog (raises RuntimeError if missing/malformed)

The service is expected to run on port 8002 — Module 3 posts purchase-avoidance
events to ``http://localhost:8002/api/v4/purchase-avoidance``.

Run locally:
    uvicorn green_coin.main:app --reload --port 8002
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from green_coin.config import settings
from green_coin.core.rewards import load_rewards
from green_coin.db.database import Base, engine

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Create tables and load the rewards catalog on startup."""
    logger.info("Green Coin Service starting up...")

    # Import models so they register with Base before create_all.
    from green_coin.db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    load_rewards(settings.REWARDS_PATH)

    logger.info("Green Coin Service ready.")
    yield
    logger.info("Green Coin Service shut down.")


app = FastAPI(
    title="Green Coin Service",
    description="Module 4 — Sustainability Credits. CO2e-backed coins for "
    "circular return dispositions, redeemable on Renewed inventory.",
    version="0.1.0",
    lifespan=lifespan,
)

# Allow the React wallet UI (dev server) to call the API during the demo.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Register routers ---
from green_coin.api.routes_coins import router as coins_router  # noqa: E402
from green_coin.api.routes_integration import router as integration_router  # noqa: E402

app.include_router(coins_router)
app.include_router(integration_router)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok", "service": "green_coin", "version": app.version}
