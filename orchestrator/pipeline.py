"""End-to-end Second Life Commerce pipeline.

Composes the five modules into the canonical flow from the README:

    return initiated
        -> Module 1  grade + fraud check  -> Health Card + disposition
        -> (fraud divert?) Module 1 p2p-choice -> Module 5 price + pickup
        -> Module 4  CO2e -> Green Coins (P2P_LOCAL earns the top reward)
        -> Module 2  recommend feed (resale supply finds a buyer)

and the pre-purchase prevention flow:

    PDP view -> Module 3 risk-score
        (-> Module 2 customer-profile, -> Module 4 purchase-avoidance reward)

Every step is best-effort and recorded in a structured trace: one module being
down degrades the result but never aborts the whole pipeline. This is the
saga/orchestrator pattern — modules stay decoupled and independently testable,
the orchestrator owns the cross-module choreography.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

from orchestrator import mappings
from orchestrator.clients import (
    GradingClient,
    GreenCoinClient,
    P2PClient,
    PreventionClient,
    RecommendClient,
)


def _err(exc: Exception) -> dict[str, Any]:
    """Render any client failure into a serializable step result."""
    if isinstance(exc, httpx.HTTPStatusError):
        detail: Any
        try:
            detail = exc.response.json()
        except Exception:
            detail = exc.response.text
        return {"ok": False, "error": f"HTTP {exc.response.status_code}", "detail": detail}
    return {"ok": False, "error": type(exc).__name__, "detail": str(exc)}


@dataclass
class PipelineResult:
    persona: str
    steps: list[dict[str, Any]] = field(default_factory=list)
    health_card: dict[str, Any] | None = None
    disposition: str | None = None
    green_coin_disposition: str | None = None
    coins_earned: int | None = None
    co2e_kg: float | None = None
    chose_p2p: bool = False
    p2p_quote: dict[str, Any] | None = None

    def step(self, name: str, result: dict[str, Any]) -> None:
        self.steps.append({"step": name, **result})

    def to_dict(self) -> dict[str, Any]:
        return {
            "persona": self.persona,
            "disposition": self.disposition,
            "green_coin_disposition": self.green_coin_disposition,
            "coins_earned": self.coins_earned,
            "co2e_kg": self.co2e_kg,
            "chose_p2p": self.chose_p2p,
            "health_card": self.health_card,
            "p2p_quote": self.p2p_quote,
            "steps": self.steps,
        }


class Orchestrator:
    def __init__(self) -> None:
        self.grading = GradingClient()
        self.recommend = RecommendClient()
        self.prevention = PreventionClient()
        self.green_coin = GreenCoinClient()
        self.p2p = P2PClient()

    # ------------------------------------------------------------------
    # The full return → grade → route → reward → recommend flow
    # ------------------------------------------------------------------
    def run_return(
        self,
        *,
        persona: str,
        order_id: str,
        product_id: str,
        customer_id: str,
        category: str,
        qa_answers: dict[str, str],
        original_price: float,
        purchase_date: str,
        warranty_remaining_months: int = 0,
        image_uris: list[str] | None = None,
        item_weight_kg: float = 0.5,
        buyer_distance_km: float = 10.0,
        prefer_p2p: bool = True,
        recommend_user_id: str | None = None,
        delivery_date: str | None = None,
        age_months: int = 6,
        connected_accounts: list[str] | None = None,
    ) -> PipelineResult:
        res = PipelineResult(persona=persona)
        image_uris = image_uris or ["s3://uploads/demo1.jpg"]

        # 1. Initiate return -------------------------------------------------
        try:
            init = self.grading.initiate(order_id, product_id, customer_id,
                                         category, delivery_date)
            return_id = init["return_id"]
            res.step("module_1.initiate", {"ok": True, "return_id": return_id,
                                           "window_days": init.get("window_days"),
                                           "days_elapsed": init.get("days_elapsed")})
        except Exception as exc:
            res.step("module_1.initiate", _err(exc))
            return res  # cannot proceed without a return session

        # 2. Submit for grading ---------------------------------------------
        catalog_metadata = {
            "category": category,
            "original_price": original_price,
            "purchase_date": purchase_date,
            "warranty_remaining_months": warranty_remaining_months,
        }
        try:
            submit = self.grading.submit(return_id, qa_answers, image_uris, catalog_metadata,
                                         connected_accounts=connected_accounts or [])
            hc = submit["health_card"]
            res.health_card = hc
            res.disposition = hc["disposition"]
            offered = submit.get("p2p_divert_offered", False)
            res.step("module_1.submit", {
                "ok": True,
                "condition": hc["condition"],
                "health_score": hc["health_score"],
                "disposition": hc["disposition"],
                "fraud_confidence": hc["fraud_signal"]["fraud_confidence"],
                "p2p_divert_offered": offered,
            })
        except Exception as exc:
            res.step("module_1.submit", _err(exc))
            return res

        # 3. P2P routing -----------------------------------------------------
        # Two ways an item reaches Module 5:
        #   (a) fraud divert — Module 1 offers it (Clothing & Footwear + high
        #       fraud_confidence) and the customer accepts; or
        #   (b) the "nearby buyer" path — a high-grade `resell` item (Gate B
        #       score > 90) is listed P2P instead of routed to a fulfillment
        #       center (README Gate B: "Resell as Renewed — or P2P if a nearby
        #       buyer exists").
        chose_p2p = False
        if offered:
            chose_p2p = prefer_p2p
            try:
                choice = self.grading.p2p_choice(return_id, chose_p2p)
                res.step("module_1.p2p_choice", {
                    "ok": True,
                    "chose_p2p": chose_p2p,
                    "source": choice["health_card"].get("source"),
                })
            except Exception as exc:
                res.step("module_1.p2p_choice", _err(exc))

        list_on_p2p = prefer_p2p and (chose_p2p or res.disposition == "resell")
        if list_on_p2p:
            listing = self._build_p2p_listing(product_id, category, original_price,
                                              age_months, hc)
            try:
                quote = self.p2p.quote(listing)
                res.p2p_quote = quote
                res.step("module_5.quote", {
                    "ok": True,
                    "via": "fraud_divert" if chose_p2p else "nearby_buyer_resell",
                    "gross_price": quote.get("gross_price"),
                    "net_payout": quote.get("net_payout"),
                    "low": quote.get("low"),
                    "high": quote.get("high"),
                    "model": quote.get("model"),
                })
                accept = self.p2p.accept(product_id)
                res.step("module_5.accept", {"ok": True,
                                              "pickup_job": accept.get("job_id"),
                                              "status": accept.get("status")})
            except Exception as exc:
                res.step("module_5.quote", _err(exc))
        res.chose_p2p = chose_p2p

        # 4. Reward via Module 4 (CO2e -> Green Coins) -----------------------
        gc_disposition = mappings.disposition_to_green_coin(res.disposition, list_on_p2p)
        res.green_coin_disposition = gc_disposition
        gc_category = mappings.category_to_green_coin(category)
        try:
            earn = self.green_coin.earn(
                user_id=customer_id,
                disposition=gc_disposition,
                category=gc_category,
                item_id=product_id,
                item_weight_kg=item_weight_kg,
                buyer_distance_km=buyer_distance_km if list_on_p2p else 0.0,
            )
            res.coins_earned = earn.get("coins_earned")
            res.co2e_kg = earn.get("co2e_kg")
            badge = earn.get("badge_unlocked")
            res.step("module_4.earn", {
                "ok": True,
                "disposition": gc_disposition,
                "coins_earned": earn.get("coins_earned"),
                "co2e_kg": earn.get("co2e_kg"),
                "new_balance": earn.get("new_balance"),
                "badge_unlocked": badge.get("name") if badge else None,
            })
        except Exception as exc:
            res.step("module_4.earn", _err(exc))

        # 5. Close the loop: recommend the resale supply to a buyer ----------
        if recommend_user_id:
            try:
                feed = self.recommend.recommend(recommend_user_id, k=5)
                top = [
                    {"sku_id": i["sku_id"], "badge": i["badge"],
                     "health_score": i["health_score"], "reasons": i["reasons"]}
                    for i in feed.get("items", [])[:5]
                ]
                res.step("module_2.recommend", {"ok": True, "user_id": recommend_user_id,
                                                "top_items": top})
            except Exception as exc:
                res.step("module_2.recommend", _err(exc))

        return res

    # ------------------------------------------------------------------
    # Pre-purchase prevention flow (Module 3 -> 2 -> 4)
    # ------------------------------------------------------------------
    def run_prevention(
        self,
        *,
        persona: str,
        customer_id: str,
        product_id: str,
        page_dwell_seconds: float = 8.0,
        is_buy_now: bool = True,
        seller_id: str | None = None,
        product_price: float | None = None,
        is_sale_active: bool = False,
        product_review_rating: float | None = None,
    ) -> dict[str, Any]:
        out: dict[str, Any] = {"persona": persona, "steps": []}

        # Confirm the profile Module 3 will read (Module 2 endpoint).
        try:
            profile = self.recommend.customer_profile(customer_id)
            out["steps"].append({"step": "module_2.customer_profile", "ok": True,
                                 "orders": len(profile.get("order_history", []))})
        except Exception as exc:
            out["steps"].append({"step": "module_2.customer_profile", **_err(exc)})

        try:
            risk = self.prevention.risk_score(
                customer_id=customer_id, product_id=product_id,
                page_dwell_seconds=page_dwell_seconds, is_buy_now=is_buy_now,
                seller_id=seller_id, product_price=product_price,
                is_sale_active=is_sale_active, product_review_rating=product_review_rating,
            )
            out["risk_score"] = risk.get("risk_score")
            out["intervention_type"] = risk.get("intervention_type")
            out["intervention_copy"] = risk.get("intervention_copy")
            out["steps"].append({"step": "module_3.risk_score", "ok": True,
                                 "risk_score": risk.get("risk_score"),
                                 "intervention_type": risk.get("intervention_type"),
                                 "taxonomy_miss": risk.get("taxonomy_miss")})
        except Exception as exc:
            out["steps"].append({"step": "module_3.risk_score", **_err(exc)})

        return out

    # ------------------------------------------------------------------
    @staticmethod
    def _build_p2p_listing(product_id: str, category: str, original_price: float,
                           age_months: int, health_card: dict) -> dict:
        hs = float(health_card.get("health_score", 70))
        return {
            "sku_id": product_id,
            "category": mappings.category_to_p2p(category),
            "original_price": original_price,
            "age_months": age_months,
            "brand_tier": mappings.brand_tier_for(hs),
            "has_box": True,
            "accessories_complete": True,
            "media_refs": [health_card.get("anomaly_heatmap_uri", "")],
            "health_card": {
                "sku_id": product_id,
                "condition": health_card.get("condition", "Good"),
                "health_score": hs,
                "confidence": health_card.get("confidence", 0.9),
                "price": round(original_price * 0.6, 2),
                "original_price": original_price,
                "is_renewed": True,
            },
        }
