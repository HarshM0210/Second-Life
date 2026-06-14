"""Thin synchronous HTTP clients — one per module.

Kept deliberately dumb: each method is a single request that returns parsed
JSON (or raises ``httpx.HTTPStatusError``). All orchestration logic lives in
``pipeline.py``; these just speak HTTP.
"""
from __future__ import annotations

from typing import Any

import httpx

from orchestrator.config import SERVICES, TIMEOUT_DEFAULT, TIMEOUT_GRADING


def _get(url: str, timeout: float = TIMEOUT_DEFAULT) -> dict[str, Any]:
    resp = httpx.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _post(url: str, payload: dict, timeout: float = TIMEOUT_DEFAULT) -> dict[str, Any]:
    resp = httpx.post(url, json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


# --- Module 1: Grading / Fraud / Quality ------------------------------------
class GradingClient:
    base = SERVICES.grading

    def initiate(self, order_id: str, product_id: str, customer_id: str,
                 category: str, delivery_date: str | None = None) -> dict:
        body = {
            "order_id": order_id,
            "product_id": product_id,
            "customer_id": customer_id,
            "category": category,
        }
        if delivery_date:
            body["delivery_date"] = delivery_date
        return _post(f"{self.base}/api/returns/initiate", body, TIMEOUT_GRADING)

    def submit(self, return_id: str, qa_answers: dict, image_uris: list[str],
               catalog_metadata: dict, video_frame_uris: list[str] | None = None,
               connected_accounts: list[str] | None = None) -> dict:
        body = {
            "qa_answers": qa_answers,
            "image_uris": image_uris,
            "video_frame_uris": video_frame_uris or [],
            "catalog_metadata": catalog_metadata,
            "connected_accounts": connected_accounts or [],
        }
        return _post(f"{self.base}/api/returns/{return_id}/submit", body, TIMEOUT_GRADING)

    def p2p_choice(self, return_id: str, chose_p2p: bool) -> dict:
        return _post(f"{self.base}/api/returns/{return_id}/p2p-choice",
                     {"chose_p2p": chose_p2p}, TIMEOUT_GRADING)


# --- Module 2: Recommend (+ Customer_Profile) -------------------------------
class RecommendClient:
    base = SERVICES.recommend

    def recommend(self, user_id: str, k: int = 10) -> dict:
        return _get(f"{self.base}/recommend?user_id={user_id}&k={k}")

    def customer_profile(self, customer_id: str) -> dict:
        return _get(f"{self.base}/api/v2/customer-profile/{customer_id}")


# --- Module 3: Return Prevention --------------------------------------------
class PreventionClient:
    base = SERVICES.prevention

    def risk_score(self, customer_id: str, product_id: str, page_dwell_seconds: float,
                   is_buy_now: bool, seller_id: str | None = None,
                   product_price: float | None = None, is_sale_active: bool = False,
                   product_review_rating: float | None = None) -> dict:
        body: dict[str, Any] = {
            "customer_id": customer_id,
            "product_id": product_id,
            "page_dwell_seconds": page_dwell_seconds,
            "is_buy_now": is_buy_now,
            "is_sale_active": is_sale_active,
        }
        if seller_id is not None:
            body["seller_id"] = seller_id
        if product_price is not None:
            body["product_price"] = product_price
        if product_review_rating is not None:
            body["product_review_rating"] = product_review_rating
        return _post(f"{self.base}/api/v1/risk-score", body)


# --- Module 4: Green Coin ----------------------------------------------------
class GreenCoinClient:
    base = SERVICES.green_coin

    def earn(self, user_id: str, disposition: str, category: str, item_id: str,
             item_weight_kg: float = 0.5, buyer_distance_km: float = 0.0) -> dict:
        return _post(f"{self.base}/api/v4/coins/earn", {
            "user_id": user_id,
            "disposition": disposition,
            "category": category,
            "item_id": item_id,
            "item_weight_kg": item_weight_kg,
            "buyer_distance_km": buyer_distance_km,
        })

    def earn_bonus(self, user_id: str, coins: int, source: str,
                   item_id: str | None = None) -> dict:
        body: dict[str, Any] = {"user_id": user_id, "coins": coins, "source": source}
        if item_id:
            body["item_id"] = item_id
        return _post(f"{self.base}/api/v4/coins/earn/bonus", body)

    def wallet(self, user_id: str) -> dict:
        return _get(f"{self.base}/api/v4/coins/wallet/{user_id}")

    def impact_summary(self) -> dict:
        return _get(f"{self.base}/api/v4/coins/impact/summary")


# --- Module 5: P2P Exchange --------------------------------------------------
class P2PClient:
    base = SERVICES.p2p

    def quote(self, listing: dict) -> dict:
        return _post(f"{self.base}/quote", listing)

    def accept(self, sku_id: str) -> dict:
        return _post(f"{self.base}/accept", {"sku_id": sku_id})

    def pickup(self, job_id: str) -> dict:
        return _get(f"{self.base}/pickup/{job_id}")
