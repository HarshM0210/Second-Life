"""Pipeline gateway — a single HTTP front door over the five modules.

Run:  uvicorn orchestrator.gateway:app --port 8080

Endpoints:
    GET  /health                 liveness of the gateway itself
    GET  /services               aggregate health of all 5 module services
    POST /pipeline/return        run the full return -> grade -> reward -> recommend flow
    POST /pipeline/prevention    run the pre-purchase return-prevention flow
"""
from __future__ import annotations

from typing import Any, Optional

import httpx
from fastapi import FastAPI
from pydantic import BaseModel

from orchestrator.config import SERVICES
from orchestrator.pipeline import Orchestrator

app = FastAPI(title="Second Life Commerce — Pipeline Gateway", version="1.0.0")
_orc = Orchestrator()


class ReturnRequest(BaseModel):
    persona: str = "demo"
    order_id: str
    product_id: str
    customer_id: str
    category: str
    qa_answers: dict[str, str]
    original_price: float
    purchase_date: str
    warranty_remaining_months: int = 0
    image_uris: Optional[list[str]] = None
    item_weight_kg: float = 0.5
    buyer_distance_km: float = 10.0
    prefer_p2p: bool = True
    recommend_user_id: Optional[str] = None
    delivery_date: Optional[str] = None
    age_months: int = 6
    connected_accounts: Optional[list[str]] = None


class PreventionRequest(BaseModel):
    persona: str = "demo"
    customer_id: str
    product_id: str
    page_dwell_seconds: float = 8.0
    is_buy_now: bool = True
    seller_id: Optional[str] = None
    product_price: Optional[float] = None
    is_sale_active: bool = False
    product_review_rating: Optional[float] = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "pipeline_gateway"}


@app.get("/services")
def services() -> dict[str, Any]:
    """Probe every module's /health endpoint."""
    out: dict[str, Any] = {}
    health_paths = {
        "module_1_grading": f"{SERVICES.grading}/health",
        "module_2_recommend": f"{SERVICES.recommend}/health",
        "module_3_prevention": f"{SERVICES.prevention}/api/v1/risk-score",  # no /health; probed below
        "module_4_green_coin": f"{SERVICES.green_coin}/health",
        "module_5_p2p": f"{SERVICES.p2p}/health",
    }
    for name, url in health_paths.items():
        if name == "module_3_prevention":
            # Module 3 has no /health; a 422 from risk-score proves it's up.
            try:
                r = httpx.post(url, json={}, timeout=3.0)
                out[name] = {"up": r.status_code in (200, 422), "status_code": r.status_code}
            except Exception as exc:
                out[name] = {"up": False, "error": type(exc).__name__}
            continue
        try:
            r = httpx.get(url, timeout=3.0)
            out[name] = {"up": r.status_code == 200, "detail": r.json() if r.status_code == 200 else r.status_code}
        except Exception as exc:
            out[name] = {"up": False, "error": type(exc).__name__}
    out["all_up"] = all(v.get("up") for v in out.values() if isinstance(v, dict))
    return out


@app.post("/pipeline/return")
def pipeline_return(req: ReturnRequest) -> dict[str, Any]:
    result = _orc.run_return(**req.model_dump())
    return result.to_dict()


@app.post("/pipeline/prevention")
def pipeline_prevention(req: PreventionRequest) -> dict[str, Any]:
    return _orc.run_prevention(**req.model_dump())
