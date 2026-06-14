# Second Life Commerce

**AI-powered returns, grading, and sustainable resale for the Amazon ecosystem.**

Every returned or unused product is automatically routed to its highest-value
next destination. We call it the **"Intelligent Bridge"** — the missing layer
for the long tail of returns that today's system simply writes off.

> Millions of products. No intelligent bridge. The system works for premium
> goods; for the long tail, it breaks. Second Life fixes that.

---

## The problem (in the organizers' own words)

The current returns system is built for premium goods. For the long tail, the
economics collapse — three personas make it concrete:

| Persona | Situation | Today's outcome |
|---|---|---|
| **Priya** | ₹500 shoes, 600 km back to the warehouse | Costs more to re-list than they're worth → **written off** |
| **Rahul** | Baby monitor, works perfectly, won't sell on classifieds (strangers, haggling) | Sits in a drawer — while 50 nearby parents want one |
| **Small Seller** | 200 returns/month, all fine, manually inspected and re-priced by guesswork | Drowns in manual work → **needs AI, not better logistics** |

**The named challenge — "Build the Intelligent Bridge" — maps 1:1 onto our modules:**

| Organizer pillar | Our module |
|---|---|
| AI Grading (instant, <2s/item, no manual inspection) | Module 1 |
| Smart Routing (resell / refurbish / P2P / donate) | Module 1 routing + Module 5 P2P |
| Trust Layer ("Product Health Card") | Module 1 output |
| Fraud Detection (wardrobing via consent-based Social Connect) | Module 1 fraud layer |
| Prevention (predict returns before they happen) | Module 3 |

We hit every pillar **and** add Green Credits — a deliberate over-delivery on
the "Think Big" axis.

---

## System overview

A central hub (`Amazon`) routes every return through five modules:

1. **Grading, Fraud Detection & Quality** — detect wardrobing fraud via Social
   Connect, grade a returned item, decide its disposition. *(Core — build first.)*
2. **Recommend** — surface refurbished + new products to the right buyer.
3. **Return Prevention** — predict and prevent bad-fit purchases before checkout.
4. **Sustainability Credits ("Green Coin")** — reward low-impact choices with
   redeemable credits.
5. **P2P Exchange** — direct buyer-to-buyer resale (Rahul's monitor → 50 nearby
   parents).

### End-to-end data flow

```
Order -> Customer -> Return trigger
                        |
              [return-window check]
                        |
        +---------------+----------------+
        |                                |
  within window                     window over
  (Q&A + img + video)            (auto disposition by score)
        |
   +----+------------------------------+
   | Social Connect Fraud Check        |  (runs in parallel)
   | AI Grader (LOCAL)                 |
   +----+------------------------------+
        |
   fraud_confidence < 0.60          fraud_confidence >= 0.60
   (genuine return)                 (wardrobing detected)
        |                                |
   Gate A: cost vs value           Offer P2P Resale path
   Gate B: health score            (non-accusatory offer screen)
        |                                |
   {return-to-seller | resell |    Customer chooses:
    refurbish | donate | recycle}  P2P (Module 5) OR standard inspection
        |
   Product Health Card -> "Certified by Amazon AI"
        |
   Recommend (match to buyer) + Green Credits issued
```

The **Product Health Card** JSON is the inter-module contract. Modules add
fields freely but never remove or rename existing ones — every downstream
module depends on field stability.

---

## The modules

### Module 1 — Grading, Fraud Detection & Quality *(core)*

The headline module; everything else hangs off its disposition decision.
Organizer target: **condition assessment in under 2 seconds per item, no manual
inspection.**

- **Structured input:** category-specific Q&A (replaces free-text reason),
  images, ~15s video, catalog metadata.
- **Social Connect fraud check** *(parallel)*: consent-based scan of public
  posts within the ownership window, emitting a `fraud_signal` with a
  `fraud_confidence` score. Degrades gracefully when no social account is linked.
- **AI Grader** *(parallel, all local — no multimodal API):* an unsupervised
  anomaly detector (`anomalib` PatchCore/FastFlow, trained only on defect-free
  images) feeds either:
  - *Option A* — a local quantized VLM (Qwen2.5-VL) for generated justifications
    (impressive, GPU-bound, higher risk), or
  - *Option B (recommended)* — a transparent weighted score + template
    justification (CPU-only, sub-2s, fully explainable).
- **Output:** a **Product Health Card** (condition, `health_score`, defects,
  anomaly heatmap, justification, `disposition`, `fraud_signal`).
- **Routing:** Gate A (economics: processing cost vs product value) then Gate B
  (health score → resell / refurbish / donate / recycle). High fraud confidence
  triggers a non-accusatory **P2P resale offer** instead of a rejection.

### Module 2 — Recommend

Surfaces **refurbished + new** products so the resale supply from Module 1
actually clears. Local embedding retrieval (`bge-small` / CLIP), cosine-ranked,
boosting high-score Renewed items into the same feed.

### Module 3 — Return Prevention

Predicts return likelihood **before purchase** and intervenes on the product
page ("Customers with your foot profile prefer size 8 in this brand"). A
lightweight return-risk scorer + per-customer fit profile + a PDP banner that
fires above a risk threshold. **Already implemented in this repo.**

### Module 4 — Sustainability Credits ("Green Coin")

The **demand-side flywheel**. Module 1 creates Renewed supply; Green Coin
creates the demand that clears it. Every coin is backed by a defensible
**kg CO₂e avoided** figure and is redeemable only on sustainability-positive
actions (overwhelmingly Renewed inventory). **Implemented in this repo —**
see [`Module-4/README.md`](Module-4/README.md).

> *"Grading creates supply. Green Coin creates demand. The long tail finally
> gets a second life."*

### Module 5 — P2P Exchange

Directly addresses Rahul. When an item grades high (>90) and a high-affinity
buyer exists nearby, list it as a P2P direct sale instead of routing through a
fulfillment center — near-zero reverse logistics, the largest CO₂e saving, and
the biggest Green Coin reward. Amazon provides the trust wrapper (Health Card +
A-to-Z guarantee + escrow).

---

## Tech stack (prototype)

- **Frontend:** React (return flow with structured Q&A, Health Card, P2P offer,
  wallet, rec feed, P2P listing). Built fast with Kiro.
- **Backend:** lightweight services (FastAPI / Python) holding routing logic,
  cost/CO₂e tables, the coin ledger, the fraud aggregator, and the wardrobing
  score writer.
- **AI — all local, no third-party multimodal API:**
  - Defect detection: `anomalib` PatchCore/FastFlow (unsupervised, no labels).
  - Wear detection: a CV layer on submitted images.
  - Condition reasoning: local quantized VLM (Option A) *or* a Q&A intent
    classifier + weighted score + templates (Option B, recommended).
  - Embeddings: local `bge-small` / CLIP for Recommend + P2P match.
  - Social fraud scan: OAuth-scoped read, ownership-window filtered, visual match.
- **Storage:** in-memory / SQLite for the demo; Postgres + S3 (media + anomaly
  heatmaps) as the production path.
- **Deploy:** AWS — a GPU instance is needed only for Option A; Option B is
  CPU-only, so the live demo has no GPU dependency.

---

## Suggested demo build order (48h)

1. **Module 1 end to end** — the whole story; shows real AI, hits the <2s target,
   demonstrates the wardrobing catch. *Build first, protect at all costs.*
2. **Module 5 P2P** — small surface area, strong narrative payoff (Rahul).
3. **Module 4 Green Coin** — easy bolt-on, very visual, owns the sustainability theme.
4. **Module 2 Recommend** — shows resale supply finding buyers (closes the loop).
5. **Module 3 Return Prevention** — strong upstream-prevention closer.

---

## Metrics to pitch

- Recovery rate per returned item (target +20–30%) — counters "written off."
- % of returns skipping physical inspection (the cost killer).
- Return-rate reduction from prevention.
- CO₂e avoided per quarter.
- Renewed GMV growth.

---

## Futuristic vision (roadmap)

- **EU Digital Product Passport (DPP):** our Health Card + Green Coin ledger is a
  DPP-ready data model — early compliance infrastructure for ESPR (2027).
- **India Green Credit Programme (GCP):** link Green Coin to the GoI LiFE
  initiative's tradable credit registry — a regulatory moat for Amazon India.
- **Real LCA data (ecoinvent / Ecochain):** replace lookup tables with
  ISO 14083-compliant per-SKU emission factors.
- **Dynamic CO₂e pricing:** route disposition through the CO₂e engine so a nearby
  P2P buyer can be preferred over an FC resell.
- **Seller-side Green Coin & gamified season events** (e.g. Diwali Green Week 2×).
- **Grading → bandit/RL routing:** "best disposition" is a delayed-reward problem,
  not a static classifier.

---

## Repository structure & status

```
Second-Life/
├─ README.md              ← you are here (project overview)
├─ Module 3/              Return Prevention — IMPLEMENTED (Python + React)
│  ├─ return_prevention/  FastAPI service (risk scoring, interventions)
│  ├─ ml/                 LightGBM model + training
│  └─ src/                React PDP banner + hooks
└─ Module-4/              Sustainability Credits — IMPLEMENTED
   ├─ green_coin/         FastAPI service (event-sourced coin ledger)
   ├─ frontend/           Self-contained React wallet UI
   ├─ data/rewards.json   Renewed-only redemption catalog
   ├─ tests/              28 unit + API tests
   ├─ README.md           Module 4 docs (run, API, integration)
   └─ SecondLIFE_README.md  Full product spec / implementation guidelines
```

| Module | Status | Location |
|---|---|---|
| 1 — Grading & Fraud | Planned (teammate) | — |
| 2 — Recommend | Planned (teammate) | — |
| 3 — Return Prevention | **Implemented** | `Module 3/` |
| 4 — Green Coin | **Implemented** | `Module-4/` |
| 5 — P2P Exchange | Planned (teammate) | — |

> Module 3 and Module 4 are already wired together: Module 3 emits
> `purchase_avoidance` events to Module 4's `/api/v4/purchase-avoidance`
> endpoint (rewarding a customer who keeps an item after a nudge).

---

## Built with Kiro

Developed for a 48-hour Amazon hackathon. Optimized for the four scoring axes:
quality of presentation, quality of implementation, technical architecture, and
futuristic vision. The full implementation spec lives in
[`Module-4/SecondLIFE_README.md`](Module-4/SecondLIFE_README.md).
