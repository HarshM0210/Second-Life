"""P2P Exchange — FastAPI service."""

import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException

from p2p import schemas, features, pricing, pickup, media

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load fixtures
    fp = Path(__file__).resolve().parent.parent / "fixtures" / "listings.json"
    if fp.exists():
        app.state.listings = json.loads(fp.read_text())
    # Warm the pricing model so /health reports its true state (cheap; <1s).
    try:
        pricing.ensure_model()
    except Exception as e:
        logger.warning("Pricing model warmup failed: %s", e)
    # CLIP stays lazy by default (avoids a heavy download on every boot); opt in
    # for the live demo with P2P_WARM_CLIP=1. /health reflects the real state either way.
    if os.environ.get("P2P_WARM_CLIP") == "1":
        try:
            media._load_model()
        except Exception as e:
            logger.warning("CLIP warmup failed: %s", e)
    yield


app = FastAPI(lifespan=lifespan)


@app.post("/quote")
def quote(body: dict):
    listing = schemas.ItemListing.from_dict(body)
    fv = features.extract_features(listing)
    result = pricing.quote(fv, sku_id=listing.sku_id)
    return result.to_dict()


@app.post("/accept")
def accept(body: dict):
    job = pickup.schedule(body["sku_id"])
    return job.to_dict()


@app.get("/pickup/{job_id}")
def get_pickup(job_id: str):
    job = pickup.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.to_dict()


@app.get("/health")
def health():
    return {
        "status": "ok",
        "module": "p2p",
        "model_loaded": bool(pricing._models),
        "clip_loaded": media.is_model_loaded(),
    }
