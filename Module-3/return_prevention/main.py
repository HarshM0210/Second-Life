"""
return_prevention/main.py

FastAPI application factory and startup/shutdown hooks for the
Return Prevention Service (Module 3).

Startup sequence:
  1. Load taxonomy from TAXONOMY_PATH
  2. Create DB tables (if not exist)
  3. Seed global seller sentinel row
  4. Load LightGBM model from MODEL_PATH
  5. Start APScheduler fit-profile aging job

If the taxonomy file or model file is missing/unpicklable, a RuntimeError
propagates and the service refuses to start.

Requirements: 1.10, 3.4, 3.7, 4.1
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from return_prevention.config import settings
from return_prevention.core.model_registry import ModelRegistry
from return_prevention.db.database import Base, SessionLocal, engine
from return_prevention.db.repositories import seed_global_seller
from return_prevention.tasks.fit_profile_aging import (
    start_aging_scheduler,
    stop_aging_scheduler,
)
from return_prevention.taxonomy.taxonomy_loader import load_taxonomy

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan context manager.

    Startup:
      1. Load taxonomy (raises RuntimeError if file missing/malformed)
      2. Create DB tables
      3. Seed global seller sentinel row
      4. Load model (raises RuntimeError if file missing/unpicklable)
      5. Start APScheduler FitProfileAgingJob

    Shutdown:
      - Stop the aging scheduler gracefully
    """
    # --- Startup ---
    logger.info("Return Prevention Service starting up...")

    # Step 1: Load taxonomy — raises RuntimeError if missing or malformed
    load_taxonomy(settings.TAXONOMY_PATH)

    # Step 2: Create all DB tables
    Base.metadata.create_all(bind=engine)

    # Step 3: Seed the global seller sentinel row
    db = SessionLocal()
    try:
        seed_global_seller(db)
    finally:
        db.close()

    # Step 4: Load ML model — raises RuntimeError if missing or unpicklable
    ModelRegistry().load(settings.MODEL_PATH)

    # Step 5: Register the fit-profile aging background job
    start_aging_scheduler()

    logger.info("Return Prevention Service ready.")

    yield

    # --- Shutdown ---
    stop_aging_scheduler()
    logger.info("Return Prevention Service shut down.")


app = FastAPI(
    title="Return Prevention Service",
    description="Module 3 — Pre-purchase return-risk scoring and intervention.",
    version="0.1.0",
    lifespan=lifespan,
)

# --- Register API routers ---
from return_prevention.api.routes_fit import router as fit_router  # noqa: E402
from return_prevention.api.routes_model import router as model_router  # noqa: E402
from return_prevention.api.routes_risk import router as risk_router  # noqa: E402

app.include_router(risk_router)
app.include_router(fit_router)
app.include_router(model_router)
