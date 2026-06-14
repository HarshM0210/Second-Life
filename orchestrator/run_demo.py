"""End-to-end demo: drives the 3-persona Second Life story across all 5 modules.

Prerequisite: all module services running (use ./run_all.sh). Then:

    python -m orchestrator.run_demo

Exits 0 only if every module was successfully exercised at least once.
"""
from __future__ import annotations

import json
import os
import sys

from orchestrator.clients import GreenCoinClient
from orchestrator.gateway import services as probe_services
from orchestrator.pipeline import Orchestrator

# Real sample media so the grader's CV layers see actual pixels (Fix 2).
_SAMPLES = os.path.abspath(os.path.join("Module 1", "backend", "storage", "samples"))
WORN_IMG = os.path.join(_SAMPLES, "worn_item.jpg")


def _hr(title: str) -> None:
    print("\n" + "=" * 72)
    print(f"  {title}")
    print("=" * 72)


def _show_steps(steps: list[dict]) -> None:
    for s in steps:
        ok = s.get("ok")
        mark = "✓" if ok else "✗"
        extra = {k: v for k, v in s.items() if k not in ("step", "ok")}
        print(f"   {mark} {s['step']:<28} {json.dumps(extra, default=str)[:160]}")


def main() -> int:
    orc = Orchestrator()
    modules_exercised: set[str] = set()

    _hr("SERVICE HEALTH")
    health = probe_services()
    print(json.dumps(health, indent=2, default=str))
    if not health.get("all_up"):
        print("\n[WARN] Not all services report healthy — continuing best-effort.")

    # ------------------------------------------------------------------
    # PRE-PURCHASE: Module 3 prevention (Priya eyeing risky shoes)
    # Pulls her profile from Module 2, emits a kept-item reward to Module 4.
    # ------------------------------------------------------------------
    _hr("PREVENTION — Priya views high-return-rate Women's Shoes")
    prev = orc.run_prevention(
        persona="priya",
        customer_id="CUST-PRIYA",
        product_id="Women's Shoes",
        page_dwell_seconds=4.0,
        is_buy_now=True,
        seller_id="SELLER-042",
        product_price=1999.0,
        is_sale_active=True,
        product_review_rating=3.2,
    )
    print(f"   risk_score        = {prev.get('risk_score')}")
    print(f"   intervention_type = {prev.get('intervention_type')}")
    print(f"   intervention_copy = {prev.get('intervention_copy')}")
    _show_steps(prev["steps"])
    for s in prev["steps"]:
        if s.get("ok") and s["step"].startswith("module_2"):
            modules_exercised.add("module_2")
        if s.get("ok") and s["step"].startswith("module_3"):
            modules_exercised.add("module_3")

    # ------------------------------------------------------------------
    # RETURNS: three personas through the full grade -> route -> reward flow
    # ------------------------------------------------------------------
    personas = [
        # Priya: ₹199 shoes, near-new (placeholder media). Gate A (clothing cost
        # ₹220 > ₹199) -> Gate B; high score -> resell -> listed P2P to a nearby
        # buyer (Module 5) -> top reward.
        dict(
            persona="priya",
            order_id="ORD-PRIYA-1", product_id="SKU-NIKE-RUN-8", customer_id="CUST-PRIYA",
            category="Clothing & Footwear", original_price=199.0, purchase_date="2026-06-01",
            warranty_remaining_months=0, item_weight_kg=0.4, prefer_p2p=True,
            buyer_distance_km=10.0, recommend_user_id="u-priya",
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
        # Maya: ₹150 destroyed dress with a REAL worn image. Honest heavy-use Q&A
        # + worn pixels -> low score -> recycle (distinct from Priya). No connected
        # accounts and no "never used" claim, so no fraud divert.
        dict(
            persona="maya",
            order_id="ORD-MAYA-1", product_id="SKU-DRESS-PARTY", customer_id="CUST-MAYA",
            category="Clothing & Footwear", original_price=150.0, purchase_date="2026-05-20",
            warranty_remaining_months=0, item_weight_kg=0.4, prefer_p2p=True,
            recommend_user_id="u-priya", image_uris=[WORN_IMG],
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
        # Rahul: ₹600 earphones, defective/partially-working. Gate A (electronics
        # cost ₹750 > ₹600) -> Gate B Good -> refurbish -> Green Coins.
        dict(
            persona="rahul",
            order_id="ORD-RAHUL-1", product_id="SKU-BABYMON-1", customer_id="CUST-RAHUL",
            category="Electronics", original_price=600.0, purchase_date="2026-05-15",
            warranty_remaining_months=8, item_weight_kg=0.6, prefer_p2p=True,
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
        # Sofia: wardrobing fraud. Claims "never worn — tags still attached" but the
        # submitted image is clearly worn, and she has connected social accounts.
        # Wear>0 + never-used claim escalates fraud_confidence >= 0.60 ->
        # p2p_divert_offered -> routed through Module 5 as p2p_fraud_divert.
        dict(
            persona="sofia-fraud",
            order_id="ORD-SOFIA-1", product_id="SKU-DESIGNER-BAG", customer_id="CUST-SOFIA",
            category="Clothing & Footwear", original_price=4999.0, purchase_date="2026-05-25",
            warranty_remaining_months=0, item_weight_kg=0.6, prefer_p2p=True,
            buyer_distance_km=6.0, recommend_user_id="u-priya", image_uris=[WORN_IMG],
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
    ]

    gc_dispositions: list[str] = []
    fraud_divert_fired = False
    for p in personas:
        _hr(f"RETURN — {p['persona']} ({p['category']}, ₹{p['original_price']:.0f})")
        result = orc.run_return(**p)
        d = result.to_dict()
        print(f"   disposition            = {d['disposition']}")
        print(f"   p2p divert chosen      = {d['chose_p2p']}")
        print(f"   green-coin disposition = {d['green_coin_disposition']}")
        print(f"   coins earned           = {d['coins_earned']}   (CO2e {d['co2e_kg']} kg)")
        if d["p2p_quote"]:
            q = d["p2p_quote"]
            print(f"   P2P quote              = gross ₹{q.get('gross_price')} "
                  f"net ₹{q.get('net_payout')} [{q.get('low')}–{q.get('high')}]")
        _show_steps(d["steps"])
        if d.get("green_coin_disposition"):
            gc_dispositions.append(d["green_coin_disposition"])
        for s in d["steps"]:
            if s.get("ok"):
                modules_exercised.add(s["step"].split(".")[0])
            if s["step"] == "module_1.submit" and s.get("p2p_divert_offered"):
                fraud_divert_fired = True

    # ------------------------------------------------------------------
    # WALLET + IMPACT (Module 4 read-back)
    # ------------------------------------------------------------------
    _hr("GREEN COIN WALLETS & PLATFORM IMPACT")
    gc = GreenCoinClient()
    for uid in ("CUST-PRIYA", "CUST-MAYA", "CUST-RAHUL", "CUST-SOFIA"):
        try:
            w = gc.wallet(uid)
            badges = [b["name"] for b in w.get("badges", []) if b.get("unlocked")]
            print(f"   {uid:<12} balance={w['balance']:<6} CO2e={w['co2e_total_kg']}kg "
                  f"badges={badges}")
        except Exception as exc:
            print(f"   {uid:<12} wallet error: {exc}")
    try:
        impact = gc.impact_summary()
        print(f"\n   PLATFORM: {impact['co2e_avoided_kg']} kg CO2e avoided · "
              f"{impact['items_given_second_life']} items given a second life · "
              f"{impact['trees_equivalent']} trees equivalent")
    except Exception as exc:
        print(f"   impact summary error: {exc}")

    # ------------------------------------------------------------------
    # VERDICT
    # ------------------------------------------------------------------
    _hr("PIPELINE VERDICT")
    expected = {"module_1", "module_2", "module_3", "module_4", "module_5"}
    print(f"   modules exercised:        {sorted(modules_exercised)}")
    print(f"   green-coin dispositions:  {gc_dispositions}")
    print(f"   distinct dispositions:    {sorted(set(gc_dispositions))}")
    print(f"   fraud divert fired:       {fraud_divert_fired}")

    checks = {
        "all 5 modules exercised": not (expected - modules_exercised),
        "disposition diversity (>1 distinct)": len(set(gc_dispositions)) > 1,
        "fraud-divert path fired": fraud_divert_fired,
    }
    for name, ok in checks.items():
        print(f"   [{'PASS' if ok else 'FAIL'}] {name}")

    if all(checks.values()):
        print("\n   [PASS] end-to-end pipeline healthy with differentiated grading.")
        return 0
    print("\n   [FAIL] one or more end-to-end checks did not pass.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
