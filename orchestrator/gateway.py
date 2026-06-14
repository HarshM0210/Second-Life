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
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from orchestrator.clients import (
    GradingClient,
    GreenCoinClient,
    P2PClient,
    PreventionClient,
    RecommendClient,
)
from orchestrator.config import SERVICES
from orchestrator.pipeline import Orchestrator

app = FastAPI(title="Second Life Commerce — Pipeline Gateway", version="1.0.0")

# Single-origin SPA: the browser only ever talks to this gateway. Allow the Vite
# dev server (and any localhost origin) during the demo.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_orc = Orchestrator()
_grading = GradingClient()
_recommend = RecommendClient()
_prevention = PreventionClient()
_green_coin = GreenCoinClient()
_p2p = P2PClient()


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


# ---------------------------------------------------------------------------
# Single-origin proxies — the SPA calls these instead of each module directly.
# Thin pass-throughs to the module clients; failures become a clean 502 body.
# ---------------------------------------------------------------------------

def _safe(call) -> Any:
    try:
        return call()
    except httpx.HTTPStatusError as exc:
        try:
            detail = exc.response.json()
        except Exception:
            detail = exc.response.text
        return JSONResponse(status_code=exc.response.status_code, content=detail)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=502,
                            content={"detail": f"{type(exc).__name__}: {exc}"})


# --- Module 4: Green Coin ---
@app.get("/api/wallet/{user_id}")
def api_wallet(user_id: str) -> Any:
    return _safe(lambda: _green_coin.wallet(user_id))


@app.get("/api/impact")
def api_impact() -> Any:
    return _safe(_green_coin.impact_summary)


@app.get("/api/rewards")
def api_rewards() -> Any:
    return _safe(lambda: httpx.get(f"{SERVICES.green_coin}/api/v4/coins/rewards",
                                   timeout=10.0).json())


class RedeemBody(BaseModel):
    user_id: str
    reward_id: str


@app.post("/api/redeem")
def api_redeem(body: RedeemBody) -> Any:
    return _safe(lambda: httpx.post(f"{SERVICES.green_coin}/api/v4/coins/redeem",
                                    json=body.model_dump(), timeout=10.0).json())


# --- Module 2: Recommend + Customer Profile ---
@app.get("/api/recommend")
def api_recommend(user_id: str, k: int = 10) -> Any:
    return _safe(lambda: _recommend.recommend(user_id, k))


@app.get("/api/customer-profile/{customer_id}")
def api_customer_profile(customer_id: str) -> Any:
    return _safe(lambda: _recommend.customer_profile(customer_id))


# --- Module 3: Return Prevention ---
class RiskBody(BaseModel):
    customer_id: str
    product_id: str
    page_dwell_seconds: float = 8.0
    is_buy_now: bool = True
    seller_id: Optional[str] = None
    product_price: Optional[float] = None
    is_sale_active: bool = False
    product_review_rating: Optional[float] = None


@app.post("/api/risk-score")
def api_risk_score(body: RiskBody) -> Any:
    return _safe(lambda: _prevention.risk_score(**body.model_dump()))


@app.get("/api/feature-importance")
def api_feature_importance() -> Any:
    return _safe(lambda: httpx.get(
        f"{SERVICES.prevention}/api/v1/model/feature-importance", timeout=10.0).json())


# --- Module 1: Grading return flow ---
class InitiateBody(BaseModel):
    order_id: str
    product_id: str
    customer_id: str
    category: str
    delivery_date: Optional[str] = None


@app.post("/api/returns/initiate")
def api_initiate(body: InitiateBody) -> Any:
    return _safe(lambda: _grading.initiate(
        body.order_id, body.product_id, body.customer_id, body.category, body.delivery_date))


class SubmitBody(BaseModel):
    qa_answers: dict[str, str]
    image_uris: list[str]
    catalog_metadata: dict[str, Any]
    video_frame_uris: Optional[list[str]] = None
    connected_accounts: Optional[list[str]] = None


@app.post("/api/returns/{return_id}/submit")
def api_submit(return_id: str, body: SubmitBody) -> Any:
    return _safe(lambda: _grading.submit(
        return_id, body.qa_answers, body.image_uris, body.catalog_metadata,
        body.video_frame_uris, body.connected_accounts))


class P2PChoiceBody(BaseModel):
    chose_p2p: bool


@app.post("/api/returns/{return_id}/p2p-choice")
def api_p2p_choice(return_id: str, body: P2PChoiceBody) -> Any:
    return _safe(lambda: _grading.p2p_choice(return_id, body.chose_p2p))


# --- Module 5: P2P pricing ---
@app.post("/api/p2p/quote")
def api_p2p_quote(listing: dict[str, Any]) -> Any:
    return _safe(lambda: _p2p.quote(listing))


class AcceptBody(BaseModel):
    sku_id: str


@app.post("/api/p2p/accept")
def api_p2p_accept(body: AcceptBody) -> Any:
    return _safe(lambda: _p2p.accept(body.sku_id))


@app.get("/api/p2p/pickup/{job_id}")
def api_p2p_pickup(job_id: str) -> Any:
    return _safe(lambda: _p2p.pickup(job_id))


# ---------------------------------------------------------------------------
# Demo scenarios — preset personas the Ops console can run as full traced
# pipelines. The worn-image path is resolved server-side so the browser never
# needs to know local file paths.
# ---------------------------------------------------------------------------
import os  # noqa: E402

_SAMPLES = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "Module 1", "backend", "storage", "samples")
)
_WORN = os.path.join(_SAMPLES, "worn_item.jpg")

SCENARIOS: dict[str, dict[str, Any]] = {
    "priya": {
        "label": "Priya — ₹199 shoes, near-new → resell → P2P",
        "payload": dict(
            persona="priya", order_id="ORD-PRIYA-1", product_id="SKU-NIKE-RUN-8",
            customer_id="CUST-PRIYA", category="Clothing & Footwear", original_price=199.0,
            purchase_date="2026-06-01", item_weight_kg=0.4, buyer_distance_km=10.0,
            recommend_user_id="u-priya",
            qa_answers={
                "return_reason": "Changed my mind",
                "wear_history": "Tried on indoors only — not worn outside",
                "tag_status": "Yes — all tags attached and intact",
                "washing_history": "No — not washed",
                "staining_odour": "No — completely clean",
                "original_packaging": "Yes — original packaging intact",
                "sole_condition": "Completely clean — no sole wear",
                "physical_damage": "No damage",
            },
        ),
    },
    "maya": {
        "label": "Maya — destroyed dress (worn image) → recycle",
        "payload": dict(
            persona="maya", order_id="ORD-MAYA-1", product_id="SKU-DRESS-PARTY",
            customer_id="CUST-MAYA", category="Clothing & Footwear", original_price=150.0,
            purchase_date="2026-05-20", item_weight_kg=0.4, recommend_user_id="u-priya",
            image_uris=[_WORN],
            qa_answers={
                "return_reason": "Changed my mind",
                "wear_history": "Worn multiple times",
                "tag_status": "All tags removed",
                "washing_history": "Yes — washed multiple times",
                "staining_odour": "Yes — visible stain or noticeable odour",
                "original_packaging": "No original packaging",
                "sole_condition": "Significant wear — clearly used outdoors",
                "physical_damage": "Significant damage (torn, broken fastening)",
            },
        ),
    },
    "rahul": {
        "label": "Rahul — ₹600 electronics, defective → refurbish",
        "payload": dict(
            persona="rahul", order_id="ORD-RAHUL-1", product_id="SKU-BABYMON-1",
            customer_id="CUST-RAHUL", category="Electronics", original_price=600.0,
            purchase_date="2026-05-15", warranty_remaining_months=8, item_weight_kg=0.6,
            buyer_distance_km=12.0, recommend_user_id="u-rahul",
            qa_answers={
                "return_reason": "Item is defective / not working",
                "functional_status": "Partially functional — some features not working",
                "physical_condition": "Minor cosmetic damage (light scratches, small dents)",
                "accessories": "Yes — all accessories present",
                "original_packaging": "Yes — original box with all inserts",
                "ownership_duration": "Used briefly (less than a week)",
                "factory_reset": "Yes — fully reset, personal data removed",
                "liquid_damage": "No — never exposed to liquid or impact",
            },
        ),
    },
    "sofia": {
        "label": "Sofia — wardrobing fraud → P2P fraud divert",
        "payload": dict(
            persona="sofia-fraud", order_id="ORD-SOFIA-1", product_id="SKU-DESIGNER-BAG",
            customer_id="CUST-SOFIA", category="Clothing & Footwear", original_price=4999.0,
            purchase_date="2026-05-25", item_weight_kg=0.6, buyer_distance_km=6.0,
            recommend_user_id="u-priya", image_uris=[_WORN],
            connected_accounts=["instagram", "facebook"],
            qa_answers={
                "return_reason": "Changed my mind",
                "wear_history": "Never worn — tags still attached",
                "tag_status": "Yes — all tags attached and intact",
                "washing_history": "No — not washed",
                "staining_odour": "No — completely clean",
                "original_packaging": "Yes — original packaging intact",
                "sole_condition": "Completely clean — no sole wear",
                "physical_damage": "No damage",
            },
        ),
    },
}


@app.get("/api/scenarios")
def api_scenarios() -> list[dict[str, str]]:
    return [{"name": k, "label": v["label"]} for k, v in SCENARIOS.items()]


@app.post("/api/scenario/{name}")
def api_scenario(name: str) -> Any:
    sc = SCENARIOS.get(name)
    if sc is None:
        return JSONResponse(status_code=404, content={"detail": f"unknown scenario: {name}"})
    return _orc.run_return(**sc["payload"]).to_dict()
