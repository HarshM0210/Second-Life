# Second Life

> AI-powered returns, grading, fraud detection, and sustainable resale for the Amazon ecosystem.
> **Every returned or unused product automatically finds its next best owner.**

---

## Hackathon Context

**Event:** HackOn with Amazon 6.0 — 48-hour Virtual Hackathon  
**Tool:** Kiro (mandatory AI IDE, kiro.dev)  
**Stack:** AWS Free Tier + local-first AI (no third-party multimodal API calls, a hard constraint and a pitch point)

### Judging Rubric

| Criterion                     | How we address it                                                                             |
| ----------------------------- | --------------------------------------------------------------------------------------------- |
| **Quality of Presentation**   | Persona Story (Rahul), live Green Coin ticker, Health Card visual, market-state demo moment   |
| **Quality of Implementation** | 5 working FastAPI services + React frontends; 600+ tests green across all modules             |
| **Technical Architecture**    | Async pipelines, event-sourced ledger, append-only contracts, graceful degradation throughout |
| **Futuristic Vision**         | EU DPP readiness, India GCP integration, LinUCB bandit, multimodal pricing, real LCA data     |

### Organizer Pillar → Module Mapping

| Organizer pillar                                              | Our module                      |
| ------------------------------------------------------------- | ------------------------------- |
| AI Grading (instant, <2s/item, no manual inspection)          | Module 1                        |
| Smart Routing (resell / refurbish / P2P / donate / recycle)   | Module 1 routing + Module 5 P2P |
| Trust Layer ("Product Health Card")                           | Module 1 output                 |
| Fraud Detection (wardrobing via consent-based Social Connect) | Module 1 fraud layer            |
| Personalised Recommendations for Renewed products             | Module 2                        |
| Return Prevention (predict before purchase)                   | Module 3                        |
| Sustainable Incentives / Green Credits                        | Module 4                        |
| Peer-to-Peer Resale inside Amazon's ecosystem                 | Module 5                        |

We hit every pillar and add Green Credits, a deliberate over-delivery on the "Think Big" axis.

---

## System Architecture Overview

```
Order → Customer → Return trigger
                        │
              [return-window check]
                        │
        ┌───────────────┴────────────────┐
        │                                │
  within window                     window over
  (Q&A + img + video)            (auto disposition by score)
        │
   ┌────┴──────────────────────────────────┐
   │ Social Connect Fraud Check (parallel) │
   │ AI Grader LOCAL (parallel)            │
   └────┬──────────────────────────────────┘
        │
   fraud_confidence < 0.60           fraud_confidence ≥ 0.60
   (genuine return)                  (wardrobing detected)
        │                                  │
   Gate A: cost vs value             Non-accusatory P2P offer
   Gate B: health score              (route to Module 5)
        │
   {return-to-seller | resell | refurbish | donate | recycle}
        │
   Product Health Card → "Certified by Amazon AI"
        │
   Module 2: Recommend (match to buyer)
   Module 4: Green Coins issued
   Module 5: P2P listing if applicable
```

### Inter-Module Ports

| Module                       | Service | Port                       |
| ---------------------------- | ------- | -------------------------- |
| Module 1 — Grading & Fraud   | FastAPI | 8000                       |
| Module 2 — Recommend         | FastAPI | 8001                       |
| Module 3 — Return Prevention | FastAPI | 8000 (separate deployment) |
| Module 4 — Green Coin        | FastAPI | 8002                       |
| Module 5 — P2P Exchange      | FastAPI | 8003                       |

### The Health Card — Master Inter-Module Contract

Module 1's sole output is consumed by all downstream modules. **Schema is append-only, fields are never removed or renamed.**

```python
class HealthCard(BaseModel):
    condition: Literal["Excellent", "Good", "Fair", "Poor"]
    health_score: int                    # 0–100
    confidence: float                    # 0.0–1.0
    warranty_left_months: int            # >= 0
    defects: list[str]
    anomaly_heatmap_uri: str             # s3://... or "" if detector failed
    justification: str
    disposition: Literal[
        "resell", "refurbish", "donate", "recycle",
        "return_to_seller", "manual_review"
    ]
    source: Literal["standard_return", "p2p_fraud_divert"]
    fraud_signal: FraudSignal

class FraudSignal(BaseModel):
    social_scan_performed: bool
    product_found_in_social: bool
    fraud_confidence: float              # 0.0–1.0
    p2p_offered: bool
    customer_chose_p2p: bool
```

**Example Health Card:**

```json
{
  "condition": "Good",
  "health_score": 78,
  "confidence": 1.0,
  "warranty_left_months": 5,
  "defects": ["sole_wear", "stains"],
  "anomaly_heatmap_uri": "s3://second-life/heatmaps/item_a1b2c3_heatmap.png",
  "justification": "Good. Detected: sole_wear, stains. Minor anomalies detected. Functional check: pass. Warranty: 5 months remaining.",
  "disposition": "refurbish",
  "source": "standard_return",
  "fraud_signal": {
    "social_scan_performed": true,
    "product_found_in_social": false,
    "fraud_confidence": 0.12,
    "p2p_offered": false,
    "customer_chose_p2p": false
  }
}
```

**Integration notes:**

- `disposition` is the routing decision — all downstream modules key off this
- `source: "p2p_fraud_divert"` signals the customer chose P2P at the fraud offer screen
- `confidence: 1.0` = all pipeline components succeeded; `0.7` = anomaly model unavailable
- `fraud_signal` block is consumed only by Module 3 (wardrobing score) and Module 5 (source flag) — all others ignore it safely
- After a P2P choice, a raw `"flags": ["enhanced_inspection"]` field may appear in the DB JSON blob — not Pydantic-validated, parse as `Optional[list[str]]`

---

## Module 1 — Grading, Fraud Detection & Quality System

**The core module. Everything else hangs off the disposition decision.**
Target: condition assessment in under 2 seconds per item, no manual inspection.

### What it solves

The "wardrobing" problem is uniquely severe in India, estimated 30–40% of fashion/footwear returns involve items worn to events and returned as new. Module 1 catches this with a consent-based Social Connect layer (consent obtained at signup, not at the accusatory moment of return), combined with CV wear detection and behavioural signals.

### Data Flow

```
Customer initiates return
        │
Return window check
        │
STEP 1: Structured Input Collection
  - Category-specific Q&A (see §Q&A below)
  - Images of item
  - Short video (~15s) of item
  - Catalog metadata: category, original price, purchase date, warranty remaining
        │
STEP 2: Social Connect Fraud Check + AI Grader (run in PARALLEL, both timeout 5s)
        │
   ┌────┴────────────────────────────────┐
   │                                     │
Product NOT found in social           Product FOUND in social
(fraud_confidence < 0.60)             (fraud_confidence ≥ 0.60)
        │                                     │
STEP 3A: Normal Disposition             STEP 3B: Non-accusatory P2P offer screen
Gate A: cost vs value                   → Customer chooses P2P or standard inspection
Gate B: health score                    → Health Card still generated (grader ran in parallel)
        │
Health Card assembled (identical schema, both paths)
        │
Modules 4 and 5 consume Health Card
```

**Pipeline internals:**

```
PipelineInput
    │
    ├─── asyncio.gather ──────────────────────────────────────┐
    │                                                          │
    │   Grader (asyncio.gather):                              │   Fraud Scanner:
    │   ├── Anomaly Detector (timeout 5s)                     │   └── scan() (timeout 5s)
    │   ├── Wear Detector (timeout 5s)                        │       Only for "Clothing & Footwear"
    │   └── Intent Classifier (timeout 5s)                    │
    │                                                          │
    └──────────────────────────────────────────────────────────┘
    │
Cross-Validation: authoritative_penalty = max(intent_penalty, wear_penalty)
    │
Health Score: 100 − (w1×anomaly + w2×defect + w3×reason + w4×authoritative_wear)
    │
Justification Engine: template rendering
    │
Fraud Aggregation: weighted_sum(social_signal, wear_penalty, behavioural_score)
                   + escalation if "never used" claim + CV wear > 0
    │
Disposition Router: priority chain → disposition enum
    │
Health Card Assembler → HealthCard
```

**Total pipeline budget: 2000ms. Component hard timeout: 5000ms each.**

### Product Categories & Return Windows

| Category            | Q&A Questions | Return Window | Fraud Scan |
| ------------------- | ------------- | ------------- | ---------- |
| Food & Grocery      | 6             | 7 days        | No         |
| Electronics         | 8             | 30 days       | No         |
| Clothing & Footwear | 8             | 15 days       | **Yes**    |
| Other               | 8             | 30 days       | No         |

Only **Clothing & Footwear** triggers the Social Connect fraud scanner and P2P divert path.

### Structured Q&A — Per Category

The Q&A replaces free-text return reason. Structured answers feed the intent classifier with zero ambiguity and are harder for fraudsters to game.

#### Food & Grocery (6 questions)

Key features: expiry date, seal integrity, storage compliance, quantity remaining.

```
Q1. Return reason: Wrong item / Damaged delivery / Expired or near expiry /
                   Quality not as expected / Allergic reaction / Other
Q2. Packaging seal: Completely sealed / Seal broken or opened
Q3. Packaging state: Fully intact / Minor damage (contents unaffected) /
                     Significant damage / Leaking or crushed
Q4. Storage compliance: Yes, stored correctly / No — conditions not met / Unsure
Q5. Expiry date: [Date picker]
Q6. Quantity remaining: 100% unused / Partially used / Mostly consumed
```

**Auto-block triggers:**

- Seal broken OR partially consumed → `recycle` (non-negotiable)
- Expired → `recycle`
- Wrong item + sealed + unexpired → `return_to_seller`

#### Electronics (8 questions)

Key features: functional status, physical damage type, accessories completeness, reset status (data privacy), warranty.

```
Q1. Return reason: Defective/not working / Not as described / Compatibility issue /
                   Changed my mind / Wrong item / Physical damage on arrival
Q2. Functional status: Fully functional / Partially functional / Not functional
Q3. Physical condition: No damage / Minor cosmetic / Moderate damage / Severe damage
Q4. Accessories: All present / Some missing [text: which?] / None included
Q5. Original packaging: Box + all inserts / Box only / No packaging
Q6. Usage duration: Never used / < 1 week / 1–4 weeks / > 1 month
Q7. Factory reset: Yes, reset / No, data still on device / Not applicable
Q8. Liquid/impact history: None / Minor liquid / Significant liquid / Dropped
```

**Auto-block triggers:**

- Factory reset = No → `manual_review` (data privacy, overrides all other gates)
- Safety concern flagged → `manual_review`

**Disposition logic:**

- Not functional + severe damage → `recycle`
- Not functional + minor damage → `refurbish` (if cost < value)
- Fully functional + complete + original box → `resell`
- Fully functional + missing accessories → `refurbish` tier

#### Clothing & Footwear (8 questions) — Highest fraud risk

Key features: wear evidence (primary wardrobing signal), tag status, washing history, sole condition (footwear).

```
Q1. Return reason: Wrong size (small/large) / Style/colour not as shown /
                   Quality not as expected / Damaged on arrival / Wrong item / Changed mind
Q2. Worn status: Never worn — tags attached / Tried on indoors only /
                 Worn once outside / Worn multiple times
Q3. Tags: All attached and intact / Some removed / All removed
Q4. Washed: Not washed / Washed once / Washed multiple times
Q5. Staining/odour: None / Minor faint mark / Visible stain or noticeable odour
Q6. Original packaging: Intact / Damaged but present / No packaging
Q7. Sole condition (footwear only): No wear / Minor dirt / Visible scuffing / Significant wear
Q8. Physical damage: None / Minor (loose thread) / Significant (torn, broken fastening)
```

**Wardrobing signal matrix:**

```
Tags removed + worn outside + washed    → High fraud confidence → P2P divert offer
"Never worn" claim + CV wear detected  → Fraud escalation (authoritative_penalty override)
Stained + washed                       → Donate if wearable, Recycle if not
Tags attached + never worn             → Resell as New
```

#### Other (8 questions) — Catch-all

Covers furniture, books, toys, sports equipment, beauty, home appliances, stationery.

```
Q1. Return reason: Defective / Not as described / Wrong item / Missing parts /
                   Changed my mind / Safety concern / Damaged on arrival
Q2. Usage: Never used / Once or twice / Regularly short period / Extensively
Q3. Condition: Like new / Good (minor use) / Fair (visible wear) / Poor (significant damage)
Q4. Parts completeness: Complete / Some missing [text: which?] / Significantly incomplete
Q5. Original packaging: Intact / Partial / None
Q6. Skin/body contact: No / Yes — not used on skin / Yes — used on skin/body
Q7. Safety concern: None / Minor concern [text] / Yes — unsafe [text]
Q8. Hygiene: No concerns / Cleaned and sanitised / May have hygiene issues
```

**Auto-block triggers:**

- Used on skin/body → block resell entirely → `donate` (score > 50) or `recycle`
- Safety concern flagged → `manual_review` (bypasses all disposition gates)

### AI Grader — Concurrent Components

Three components run concurrently via `asyncio.gather`. A **local computer vision pipeline** inspects submitted images for anomalies, defects, and wear patterns, while a **structured Q&A flow** captures the customer's self-reported condition. Both run in parallel and their results are combined to produce the final health score.

**Health score formula:**

```
health_score = 100 − (w1·anomaly_severity        # anomaly detector (heuristic or DINOv2)
                    +  w2·defect_penalty          # YOLOv9/ViT (optional)
                    +  w3·return_reason_penalty   # Q&A intent classifier
                    +  w4·wear_detection_penalty) # CV wear analysis on submitted images
```

A **cross-validation layer** takes `max(intent_penalty, wear_penalty)` as the authoritative wear signal, ensuring that self-serving Q&A answers cannot override physical evidence captured by the CV pipeline.

#### Anomaly Detector — Two Backends

The anomaly detector can run on a cutting-edge, **training-free DINOv2 backend** (ViT-S/14 with registers) that compares image patch features against a per-category "known-good" memory bank and **ensembles pessimistically** with the OpenCV heuristic:

```
final_severity = max(model_severity, heuristic_severity)
```

The DINOv2 backend is **opt-in via `ANOMALY_BACKEND=dinov2`**, with **graceful fallback** to the OpenCV heuristic when `torch`/weights are unavailable. Per-category reference ("known-good") images live in `storage/dinov2/refs/<category>/`.

| Backend            | How it works                                                                       | Requirements                  |
| ------------------ | ---------------------------------------------------------------------------------- | ----------------------------- |
| OpenCV heuristic   | Classical CV severity estimate (always available)                                  | None                          |
| DINOv2 (opt-in)    | ViT-S/14 + registers patch features vs per-category known-good memory bank         | `torch` + weights; else falls back |

> The two backends are not mutually exclusive: when DINOv2 is enabled, both run and the final severity is the pessimistic `max` of the two.

#### Score components (classical, CPU-fine, sub-2s)

- `anomaly_severity` — OpenCV heuristic, optionally ensembled with the DINOv2 backend (always available, no labels)
- `defect_penalty` — optional YOLOv9/ViT defect classifier (scratch/crack/dent/stain); skip if no labeled dataset
- `return_reason_penalty` — scikit-learn logistic regression or keyword map on Q&A answers
- `wear_detection_penalty` — CV layer detecting sole wear, fabric stress, stains, tag condition
- Justification: template engine (`"{condition}. Detected: {defect_list}. {anomaly_phrase}. Functional check: {pass/fail}. Warranty: {n} months remaining."`)
- **Pros:** CPU-fine; sub-2s; fully explainable (score-breakdown bar); never crashes demo

> **Leanest path (zero labels, zero GPU):** heuristic anomaly score + Q&A keyword classifier + wear penalty + template justification. Enable `ANOMALY_BACKEND=dinov2` for the stronger, training-free DINOv2 anomaly signal when `torch`/weights are present.

### Social Connect Fraud Layer

Consent obtained **at signup** (not at return time) — user connects Instagram/Facebook for product discovery benefits. This makes the fraud check invisible and non-accusatory.

**What it checks (Clothing & Footwear only):**

- Scans only **public** posts on connected profiles
- Scope: ownership window (purchase date → return initiation date) only
- Visual match of returned product against Amazon catalog reference images via OAuth (no scraping)

**Fraud confidence aggregation:**

```
fraud_confidence = weighted_sum(
    social_signal (0–0.40),       # found in social posts
    wear_penalty (0–0.30),        # CV wear detection
    behavioural_score (0–0.30)    # Friday-buy Monday-return pattern, repeat returns
)
+ escalation if "never used" claim AND wear_penalty > 0
```

**P2P divert offer (fraud_confidence ≥ 0.60):**

```
"We noticed this item may have been used.
 Instead of a standard return, would you like to
 resell it directly to another customer?

 You'll receive Green Credits + a partial refund
 equivalent to the resale value.

 [Resell via ReLoop P2P]   [Proceed with standard return inspection]"
```

Amazon never explicitly accuses. The offer is a carrot, not a stick. Either path produces a Health Card.

### Disposition Routing — Priority Chain

| Priority | Rule                                                       | Disposition                        | Gate               |
| -------- | ---------------------------------------------------------- | ---------------------------------- | ------------------ |
| 1        | Safety concern flagged in Q&A OR significant liquid damage | `manual_review`                    | Safety Hold        |
| 2        | Food: seal broken OR partially consumed                    | `recycle`                          | Category Override  |
| 2        | Food: expired                                              | `recycle`                          | Category Override  |
| 2        | Food: sealed + unexpired + wrong item                      | `return_to_seller`                 | Category Override  |
| 3        | Electronics: factory reset = No                            | `manual_review`                    | Safety Hold        |
| 4        | Other: used on skin/body                                   | `donate` (score > 50) or `recycle` | Category Override  |
| 5        | total_processing_cost ≥ product_value                      | `return_to_seller`                 | Economic Viability |
| 5        | unknown category                                           | `manual_review`                    | Economic Viability |
| 6        | score > 90                                                 | `resell`                           | Condition Routing  |
| 6        | score > 70 (Electronics only)                              | `refurbish`                        | Condition Routing  |
| 6        | score > 50                                                 | `donate`                           | Condition Routing  |
| 6        | score ≤ 50                                                 | `recycle`                          | Condition Routing  |

`total_processing_cost` = reverse logistics + inspection + refurb labor + storage (lookup table per category).

**Gate explanations:**

- **Safety Hold** — Overrides everything. Items with safety risks or unwiped electronics go to manual review regardless of condition or value.
- **Category Override** — Category-specific rules that bypass generic scoring (food hygiene, skin-contact items, etc.).
- **Economic Viability** — Checks whether the cost to process the item (logistics + inspection + refurb + storage) is justified by its market value. If not, the item is returned to the seller rather than processed at a loss.
- **Condition Routing** — Items that clear the economic check are routed based on their AI health score (0–100): items above 90 are marked for **resell**, items above 70 are marked for **refurbishment** (Electronics only), items above 50 for **donation**, and items scoring 50 or below for **recycling**.

### Error Handling & Graceful Degradation

| Component Failure              | Fallback                           | Effect on Health Card                                        |
| ------------------------------ | ---------------------------------- | ------------------------------------------------------------ |
| Anomaly model not found        | severity=0.0                       | confidence=0.7; defects includes "anomaly_model_unavailable" |
| Anomaly detector crash/timeout | severity=1.0 (worst case)          | Low score; defects includes failure reason                   |
| Wear detector failure          | penalty=0.0                        | No wear contribution to score                                |
| Intent classifier failure      | penalty=0.15 (medium default)      | Medium penalty applied                                       |
| Fraud scanner failure          | social_scan_performed=false        | fraud_confidence from wear+behavioural only                  |
| All 3 grader components fail   | **PipelineError** (no Health Card) | HTTP 500                                                     |
| Social not connected           | social_scan_performed=false        | No penalty; system degrades gracefully                       |

### REST API

Base URL: `http://localhost:8000` | Prefix: `/api/returns`

**`POST /api/returns/initiate`** — validates return window, returns category-specific Q&A questions  
**`POST /api/returns/{return_id}/submit`** — submits Q&A + media URIs, runs full pipeline, returns Health Card  
**`POST /api/returns/{return_id}/p2p-choice`** — records customer's P2P decision, mutates Health Card source/flags

### Environment Variables

| Variable                       | Default             | Description                                       |
| ------------------------------ | ------------------- | ------------------------------------------------- |
| `DATABASE_PATH`                | `second_life.db`    | SQLite path                                       |
| `STORAGE_BASE_PATH`            | `storage/`          | Local media root                                  |
| `STORAGE_URI_PREFIX`           | `s3://second-life/` | URI prefix for stored files                       |
| `ANOMALY_MODEL_BASE_PATH`      | `models/`           | PatchCore model directory                         |
| `ANOMALY_BACKEND`              | `heuristic`         | Anomaly backend: `heuristic` or `dinov2` (DINOv2 ViT-S/14 w/ registers; falls back to heuristic if torch/weights missing) |
| `ANOMALY_DEMO_MODE`            | `true`              | If true, simulates anomaly with OpenCV heuristics |
| `ANOMALY_INFERENCE_TIMEOUT_MS` | `1500`              | Anomaly detection timeout                         |

### Running Module 1

```bash
cd "Module 1/backend"
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend
cd "Module 1/frontend"
npm install && npm run dev   # http://localhost:5173, proxies /api → :8000

# Tests
python -m pytest tests/ -v  # 427 tests, ~3 seconds
```

### Demo Mode Limitations

- `delivery_date` and `category` passed in request body (mock order lookup)
- `connected_accounts` always empty (no real OAuth)
- Image URIs accepted but pixel analysis uses placeholder 224×224 black images
- Fraud scanner produces deterministic results seeded by `customer_id`

---

## Module 2 — Recommend

**Surfaces refurbished and Renewed products to the right buyer. The demand-creation layer.**
All inference is local — no external API.

### Pipeline

```
UserContext ──▶ profile.assemble_profile_text ──▶ embedder.embed_text ──┐
   (+ consent-gated social signals)                                      ▼
catalog text ─▶ embedder.embed_catalog (precomputed once) ─▶ retrieve.retrieve (cosine)
                                                                         ▼
                          [optional cross-encoder] ─▶ rerank (Renewed/health boost) ──▶ Feed
```

### Models

#### Text Embedding — `Alibaba-NLP/gte-modernbert-base`

| Parameter                           | Value                                        |
| ----------------------------------- | -------------------------------------------- |
| Dimension                           | 768                                          |
| Normalization                       | L2 unit vectors                              |
| Batch size                          | 64                                           |
| Runtime                             | sentence-transformers, CPU-fine, lazy-loaded |
| NDCG@10 (ESCI, 50 pooled negatives) | **0.4660** vs bge-small 0.4634               |

Phase 2.1 upgrade from `bge-small-en-v1.5`. Win is real but marginal (+0.0026 NDCG) — bge-small remains a valid lighter fallback.

#### Cross-Encoder Reranker — `Qwen/Qwen3-Reranker-0.6B` (opt-in, default OFF)

Re-scores top-20 candidates after retrieval. Flat on ESCI vs retrieval-only (0.4656 vs 0.4660) — off by default. ~1.2 GB, CPU-runnable.

#### Hash-embed fallback

Deterministic bag-of-words hashed into dim=768 buckets. Zero model download, shape/determinism stand-in only. Service **fails loud** at startup if this path is the only one available (`validate_embedder()` density check).

### Re-ranking Formula

```
final_score = cosine_similarity
            + renewed_boost_weight · clamp((health_score − floor) / (ceil − floor), 0, 1)
            + discount_boost_weight · discount_frac    # only if discount > 0
```

| Parameter               | Value | Rationale                                                                                      |
| ----------------------- | ----- | ---------------------------------------------------------------------------------------------- |
| `renewed_boost_weight`  | 0.18  | Sized so >90 Renewed Nike clears equivalent New Nike by ~14% — visible gap, not dominant       |
| `health_score_floor`    | 70.0  | Mirrors Module 1's "refurbish then list" threshold; only up-rank inventory good enough to sell |
| `health_score_ceil`     | 100.0 | Proportional ramp                                                                              |
| `discount_boost_weight` | 0.04  | ~4× smaller than health — a price cut nudges, doesn't dominate                                 |
| `min_confidence`        | 0.30  | Don't boost what the grader itself is unsure about                                             |

Boost applies **only** when `is_renewed`, `confidence ≥ min_confidence`, and `health_score ≥ floor`.

### Profile Assembly

| Signal                           | Weight                               |
| -------------------------------- | ------------------------------------ |
| Wishlist                         | 2× (current intent)                  |
| Search history                   | 2× (current intent)                  |
| Purchase history                 | 1× (weaker/staler)                   |
| Trends                           | 1×                                   |
| Social interests (consent-gated) | 2× follows/likes, 1× topics/captions |

### Social Signals (consent-gated)

Connected social activity feeds the same `profile → embed → retrieve → rerank` pipeline — no new model or ranking path.

- `SocialProfile.active = True` **only** when `consent=True` AND signal present
- `consent=False` → `extract_social_text` returns `""` → complete no-op (verified)
- Mock connector only — no real OAuth or scraping built
- Per-item reason string `"matches your social interests"` also consent-gated

### Eval Results (Phase 2.1, 2026-06-13)

| Stage      | Model                       | NDCG@10    | Recall@10  | MRR        |
| ---------- | --------------------------- | ---------- | ---------- | ---------- |
| Baseline   | `bge-small-en-v1.5` (384)   | 0.4634     | **0.5275** | 0.4899     |
| Embedder   | `gte-modernbert-base` (768) | **0.4660** | 0.5220     | **0.4938** |
| + Reranker | + `Qwen3-Reranker-0.6B`     | 0.4656     | 0.4967     | 0.4935     |

### Market-Aware Policy Demo Moment

| Market state                   | Nike-R score gap over Nike (New) | Effect                         |
| ------------------------------ | -------------------------------- | ------------------------------ |
| Normal                         | +14.6%                           | Baseline                       |
| Inventory glut (0.95)          | **+21.5%**                       | Stronger push to clear Renewed |
| High demand + costly logistics | +11.9%                           | Less push needed               |

Toggling market signals visibly flips the Renewed boost with explainable reasons. Rule-based — LinUCB bandit is future work.

### Data

100% synthetic — 8 hand-authored SKUs, 8 Health Cards, 4 personas in `fixtures/`. Embeddings are real gte-modernbert vectors. Real data is a config swap (`RECOMMEND_CATALOG` / `RECOMMEND_HEALTH_CARDS` env vars).

### Test Coverage: 108 green (90 base + 15 social + Phase 2.1)

### Running Module 2

```bash
cd "Module 2"
pip install -r requirements.txt
uvicorn recommend.main:app --reload --port 8001

python -m scripts.run_eval   # reproduce ESCI eval
```

---

## Module 3 — Return Prevention

**AI-powered pre-purchase intervention. Predicts return likelihood before checkout, shows targeted guidance on the Product Detail Page.**

Key metrics: risk scoring < 300ms | AUC-ROC: **0.9790** | zero external API calls

### Architecture

```
Browser (React PDP)
    │ "Add to Cart" / "Buy Now" click
    │ + page_dwell_seconds + is_buy_now
    ▼
FastAPI — POST /api/v1/risk-score
    │
    ├── Feature Assembler (9 features)
    │       ├── Category Taxonomy (in-memory)
    │       ├── Customer Profile Client (Module 2, read-only, 500ms timeout)
    │       ├── Price Band Profile (local DB)
    │       └── Seller Profile (local DB)
    │
    ├── Risk Scorer (LightGBM predict_proba)
    ├── Intervention Generator (template strings)
    └── Green Coin Emitter (async, non-blocking → Module 4)
```

### ML Model — LightGBM Binary Classifier

Predicts P(return | features).

**9-feature vector:**

| #   | Feature                          | Source                 | Fallback            |
| --- | -------------------------------- | ---------------------- | ------------------- |
| 1   | `category_return_rate`           | Category Taxonomy      | Global default 0.20 |
| 2   | `user_category_return_rate`      | Customer order history | Category mean       |
| 3   | `in_user_high_return_price_band` | Price Band Profile     | `false`             |
| 4   | `has_size_ambiguity`             | Category Taxonomy      | `false`             |
| 5   | `page_dwell_seconds`             | Client-side PDP timer  | Required            |
| 6   | `is_buy_now`                     | Which button clicked   | Required            |
| 7   | `product_review_rating`          | Product catalog        | 3.5                 |
| 8   | `seller_return_rate`             | Seller Profile table   | Global mean 0.15    |
| 9   | `is_sale_active`                 | Promotions flag        | `false`             |

**Training:** 10,000 synthetic samples, 80/20 stratified split, 300 estimators, lr=0.05, max_depth=6, num_leaves=31. AUC-ROC: 0.9790, Log-loss: 0.1178.

**Feature importance (gain):** product_review_rating (1781) > user_category_return_rate (1754) > category_return_rate (1413) > page_dwell_seconds (1281) > seller_return_rate (1251).

### Intervention Types

| Intervention       | Trigger                                              |
| ------------------ | ---------------------------------------------------- |
| `SIZE_GUIDANCE`    | has_size_ambiguity=true + user fit profile available |
| `SOCIAL_PROOF`     | High-rated product + low user dwell                  |
| `COMPARISON_NUDGE` | Impulse buy signal (is_buy_now + low dwell)          |
| `CLARIFYING_QA`    | Not-as-described risk (seller_return_rate high)      |

Banner renders above "Add to Cart" within 100ms. Risk scoring is **non-blocking** — checkout proceeds immediately.

### API

**`POST /api/v1/risk-score`** — returns `risk_score`, `intervention_type`, `intervention_copy`, `taxonomy_miss`  
**`GET /api/v1/fit-profile/{customer_id}`** — returns size history grouped by brand  
**`POST /api/v1/model/reload`** — hot-swap model without restart  
**`GET /api/v1/model/feature-importance`** — exposes gain scores

> **Taxonomy note:** in this prototype, `product_id` maps directly to a subcategory key in `data/taxonomy.json`. Valid keys: `"Women's Shoes"`, `"Men's Jeans"`, `"T-Shirts"`, `"Smartphones"`, `"Earphones"`, `"Tablets"`, `"Blenders"`, `"Coffee Makers"`, `"Novels"`, `"Textbooks"` etc.

### Module 4 Integration — Purchase Avoidance Events

Module 3 fires `POST {GREEN_COIN_BASE_URL}/api/v4/purchase-avoidance` asynchronously (non-blocking, one retry after 60s, then JSONL log).

**Green Coin tiers (owned by Module 4):**

| Risk Score   | Coins awarded |
| ------------ | ------------- |
| [0.60, 0.75) | 10            |
| [0.75, 0.90) | 25            |
| [0.90, 1.00] | 50            |

### Error Handling

| Scenario                              | Behavior                           | HTTP      |
| ------------------------------------- | ---------------------------------- | --------- |
| Model file missing at startup         | Refuse to start                    | —         |
| Taxonomy file missing at startup      | Refuse to start                    | —         |
| Customer Profile unreachable (>500ms) | Use category baseline; proceed     | 200       |
| Unknown seller                        | Use global mean (0.15)             | 200       |
| Product not in taxonomy               | risk_score=0.0, taxonomy_miss=true | 200       |
| Missing required field                | Pydantic validation                | 422       |
| DB failure during scoring             | Service unavailable                | 503       |
| Green Coin Service down               | Log + retry after 60s              | — (async) |

### Running Module 3

```bash
cd "Module 3"
pip install -r return_prevention/requirements.txt
python ml/synthesize_dataset.py   # generate training data
python ml/train.py                # train LightGBM, saves .pkl + report
uvicorn return_prevention.main:app --reload --port 8000

# Tests
pytest   # unit + property-based (Hypothesis, 16 correctness properties) + integration
```

**Environment variables:**

```env
MODEL_PATH=ml/models/lgbm_return_risk.pkl
RISK_THRESHOLD=0.6
DB_URL=sqlite:///./return_prevention.db
TAXONOMY_PATH=data/taxonomy.json
CUSTOMER_PROFILE_BASE_URL=http://localhost:8001
GREEN_COIN_BASE_URL=http://localhost:8002
```

---

## Module 4 — Green Coin (Sustainability Credits)

**The demand-side flywheel.** Module 1 creates Renewed supply. Green Coin creates the demand that clears it.

### Why Amazon gives coins away — 3 economic benefits

1. **Reverse-logistics savings** — rewarding local disposition (donate/P2P/keep) avoids a ₹400–600 truck journey; Amazon issues tens of rupees in coins to save hundreds
2. **Renewed demand subsidy** — coins redeem only on Renewed inventory, so every redemption clears one more second-hand item at near-zero acquisition cost
3. **Sustainability reporting** — every coin is backed by an auditable kg CO₂e avoided number from a tamper-evident ledger

### Architecture

Single FastAPI service on port 8002. Pure domain core (no I/O) — fully unit-testable.

```
HTTP (JSON)
    │
api/ (FastAPI routes)           # routes_coins.py, routes_integration.py
    │
core/ledger_service             # earn/redeem orchestration
    ├── core/co2e_engine        # CO₂e/coin math (pure functions)
    ├── core/gamification       # streak multipliers + badges (pure functions)
    ├── core/rewards            # catalog loader (cached singleton)
    └── db/repositories         # append-only ledger reads/writes
```

### Data Model — Event-Sourced Ledger

**The ledger is append-only.** Balance = `SUM(amount)`. Nothing ever updated in place.

`coin_events` table:

| Column       | Type            | Notes                                                                      |
| ------------ | --------------- | -------------------------------------------------------------------------- |
| `id`         | TEXT (PK)       | uuid4                                                                      |
| `user_id`    | TEXT            | indexed                                                                    |
| `event_type` | TEXT            | `earned` / `redeemed` / `expired` / `badge_earned`                         |
| `amount`     | INTEGER         | `+` earned, `−` redeemed/expired, `0` for badge_earned                     |
| `source`     | TEXT            | e.g. `disposition:DONATE_LOCAL`, `bonus:chose_renewed`, `badge:seed_saver` |
| `co2e_kg`    | REAL            | kg CO₂e avoided (0.0 for non-earn events)                                  |
| `streak_day` | INTEGER         | streak at time of event                                                    |
| `badge`      | TEXT (nullable) | badge slug if this event unlocked one                                      |
| `item_id`    | TEXT (nullable) | order/item reference                                                       |
| `created_at` | DATETIME        | UTC, server-defaulted                                                      |

### CO₂e Engine (Pure Functions)

```
Dispositions: P2P_LOCAL | DONATE_LOCAL | KEEP | REFURBISH | RESELL | RECYCLE | RETURN_FC
```

`RETURN_FC` = baseline (zero coins). All others measured as avoidance relative to it.

**Key constants:**

| Constant                  | Value                                                                                          | Source                       |
| ------------------------- | ---------------------------------------------------------------------------------------------- | ---------------------------- |
| `EF_ROAD_KG_PER_KG_KM`    | 0.089/1000                                                                                     | GLEC Framework / ISO 14083   |
| `BASELINE_DISTANCE_KM`    | 300                                                                                            | avg one-way to FC            |
| `BASELINE_ITEM_WEIGHT_KG` | 0.5                                                                                            | configurable per category    |
| `COIN_MULTIPLIER`         | 10                                                                                             | 1 kg CO₂e avoided = 10 coins |
| `MANUFACTURE_AVOIDED`     | electronics 45 / appliances 30 / clothing 12 / footwear 8 / toys 5 / books 1.5 / default 10 kg | LCA literature               |

### Gamification

**Streaks:** consecutive earn days multiply coins. Reset if no earn within 48h.

| Streak day | Multiplier |
| ---------- | ---------- |
| 1          | 1.0×       |
| 3          | 1.25×      |
| 7          | 1.5×       |
| 14         | 2.0×       |

**Badges (derived from lifetime CO₂e):**

| Badge              | Slug              | Threshold   |
| ------------------ | ----------------- | ----------- |
| 🌱 Seed Saver      | `seed_saver`      | 5 kg CO₂e   |
| 🌿 Eco Warrior     | `eco_warrior`     | 25 kg CO₂e  |
| 🌳 Forest Friend   | `forest_friend`   | 100 kg CO₂e |
| 🌍 Planet Guardian | `planet_guardian` | 500 kg CO₂e |

### Inter-Module Integration

| Module                | Direction    | Endpoint                          | Payload                                  |
| --------------------- | ------------ | --------------------------------- | ---------------------------------------- |
| Module 1 (Grading)    | → Green Coin | `POST /api/v4/coins/earn`         | disposition + category + item            |
| Module 3 (Prevention) | → Green Coin | `POST /api/v4/purchase-avoidance` | `PurchaseAvoidanceEvent` (already wired) |
| Module 2 (Recommend)  | → Green Coin | `POST /api/v4/coins/earn/bonus`   | `source: "chose_renewed"` (+50)          |
| Module 5 (P2P)        | → Green Coin | `POST /api/v4/coins/earn/bonus`   | `source: "p2p_referral"` (+25)           |

> **Port alignment critical:** Module 3 hardcodes `GREEN_COIN_BASE_URL=http://localhost:8002`. This service must run on 8002.

### Anti-Abuse Guardrails

- **Per-event earn cap:** 500 coins — prevents gaming via inflated fake returns
- **24h fraud flag:** earnings > 2000 coins/day → `flagged_for_review: true` (earn still honoured, warning logged)
- **Non-cashable:** account-bound, Renewed-only redemption — outside financial regulation
- **Append-only ledger:** expiry/reversals are negative events, never history rewrites

### Key API Endpoints

- `POST /api/v4/coins/earn` — earn coins from a disposition event
- `POST /api/v4/coins/earn/bonus` — bonus earn (chose Renewed, P2P referral)
- `POST /api/v4/coins/redeem` — redeem coins for a reward
- `GET /api/v4/coins/wallet/{user_id}` — balance + CO₂e + badges + history
- `GET /api/v4/coins/impact/summary` — platform-wide totals (powers live demo ticker)
- `GET /api/v4/coins/rewards` — redeemable catalog
- `POST /api/v4/purchase-avoidance` — consumed by Module 3

### Configuration

| Setting                  | Default                     | Purpose             |
| ------------------------ | --------------------------- | ------------------- |
| `DB_URL`                 | `sqlite:///./green_coin.db` | database            |
| `COIN_MULTIPLIER`        | `10`                        | coins per kg CO₂e   |
| `EARN_CAP_PER_EVENT`     | `500`                       | max coins per earn  |
| `FRAUD_DAILY_THRESHOLD`  | `2000`                      | 24h fraud flag      |
| `KEPT_AFTER_NUDGE_COINS` | `40`                        | Module 3 reward     |
| `STREAK_RESET_HOURS`     | `48`                        | streak reset window |

### Frontend Wallet

`frontend/wallet.html` — self-contained React app (no build step, CDN React + Babel). Components: live Impact Ticker (polls `/impact/summary` every 10s), animated balance Hero, Disposition Simulator (Priya's demo moment), Transaction Timeline, Badge Shelf, Redeem Catalog. Demo user hardcoded as `priya`.

### Running Module 4

```bash
cd Module-4
pip install -r green_coin/requirements.txt
uvicorn green_coin.main:app --reload --port 8002
# Open frontend/wallet.html in browser

python -m pytest -q   # 28 tests
```

---

## Module 5 — P2P Exchange

**Direct buyer-to-seller resale inside Amazon's trusted ecosystem. Directly addresses Rahul's persona.**

### What It Does

A seller offers a returned/unused item → the system predicts the **P2P resale price** (point estimate + calibrated low/high range + confidence), shows the seller their **net payout** (gross − Amazon facilitation fee), and on **Accept** schedules a mock courier pickup. No FC involvement — near-zero reverse-logistics cost and the largest CO₂e saving.

### Pipeline

```
ItemListing ─▶ features.extract_features (dual-path) ─▶ pricing.quote ─▶ PriceQuote
                   │  HealthCard? ── yes ─▶ health_score                (point+range+net payout)
                   └─ no ─▶ media.score_condition (CLIP zero-shot)
                                       │
                                       ▼
                          model.PriceModel (neural quantile-MLP)
POST /accept ─▶ pickup.schedule ─▶ PickupJob (scheduled, mock courier)
```

### Condition Scoring — Dual Path

**Path 1 (preferred):** Module 1's Health Card — `health_score` used directly as `condition_score`.

**Path 2 (fallback, no Health Card):** Local CLIP zero-shot scoring.

| Parameter   | Value                                                                         |
| ----------- | ----------------------------------------------------------------------------- |
| Model       | `clip-ViT-B-32` via `sentence-transformers`                                   |
| Output      | condition 0–100 from image-text similarity                                    |
| Prompts     | 5 prompts ("brand new unused" → 95 … "poor condition" → 30), softmax-weighted |
| Multi-frame | 80% mean + 20% worst-frame                                                    |
| Fallback    | neutral 50.0 + `is_model_loaded()=False` if torch/CLIP absent                 |

**Bug fixed (Phase A):** CPU/CUDA tensor mismatch silently pinned every Direct score to 50.0 on GPU machines — now device-aligned and verified.

### Feature Vector (7 features, same for both condition paths)

| Feature                   | Source                                                               |
| ------------------------- | -------------------------------------------------------------------- |
| `condition_score` (0–100) | CLIP or Health Card                                                  |
| `original_price`          | listing metadata                                                     |
| `age_months`              | listing metadata                                                     |
| `category_demand`         | `config.category_tables` lookup                                      |
| `category_depreciation`   | `config.category_tables` lookup                                      |
| `brand_multiplier`        | `config.brand_multipliers` (premium 1.2 / standard 1.0 / value 0.85) |
| `completeness`            | has_box + accessories flag                                           |

### Pricing Model — Neural Quantile-MLP

| Parameter      | Value                                                                                            |
| -------------- | ------------------------------------------------------------------------------------------------ |
| Architecture   | Periodic/PLR numeric embeddings → MLP (256×2, ReLU, dropout 0.1) → 3 pinball heads (q10/q50/q90) |
| Type           | Single network — no boosting, no bagging, no ensemble (post-2023 constraint)                     |
| Calibration    | Conformal Quantile Regression (CQR) — 15% calibration split, 80% coverage target                 |
| Training space | log1p-price; predictions exponentiated back                                                      |
| Artifact       | `models/quantile_mlp.pt` (weights + scaler + cal_scale) — regenerable via `python -m p2p.train`  |

**Why CQR:** flexible net interpolates each point → quantile heads collapse together → coverage crashed to ~0.04. Dropout alone was a bimodal knob (the wrong tool). CQR picks one scale factor targeting 80% coverage. **Coverage calibrated to 0.80.**

**Why not alternatives:**

- TabPFN v2 — gates weight download behind `TABPFN_TOKEN` (external credential); context cap ~10k rows
- GBM/XGBoost/LightGBM — excluded by ensemble constraint; kept only as eval baseline

### Data — Synthetic

Trained on synthetic generator (`p2p/synth.py`) — nonlinear condition curve, demand×age interaction, heteroscedastic multiplicative noise. 30,000 rows.

Real datasets evaluated and rejected:

- MerRec (real Mercari) — 166 GB total, CC-BY-NC; loader built + validated then removed
- Amazon item-price lite (~13 MB) — text→price only, no condition signal

Swapping real data in later is a drop-in for `synth.generate_xy`.

### Held-Out Results

| Model                           | MAE     | R²        | RMSLE     | 80%-coverage |
| ------------------------------- | ------- | --------- | --------- | ------------ |
| baseline quantile-GBM (retired) | 318     | 0.963     | 0.135     | 0.78         |
| **neural quantile-MLP (live)**  | **292** | **0.968** | **0.122** | **0.80**     |

MLP beats GBM on every metric and is better-calibrated.

### Quote Assembly & Net Payout

`pricing.quote(fv) → PriceQuote`: q50 → `gross_price`, q10/q90 → `low`/`high`, `confidence = 1 − (high−low)/gross` (clamped). Net payout: `fee = round(gross × 0.12)`, `net = gross − fee`. Single rounding source — structured fields and reason text always agree. Interval guard (`min_interval_frac=0.03`) keeps `low ≤ gross ≤ high`. Every quote labeled with source (`model = "neural-quantile-mlp" | "heuristic-fallback"`).

### REST API

- `POST /quote` — ItemListing → PriceQuote (point + range + net payout)
- `POST /accept` — PriceQuote → PickupJob (schedules mock courier)
- `GET /pickup/{id}` — pickup status
- `GET /health` — `model_loaded` / `clip_loaded` (real lazy-load state)

### All Tunables

| Parameter                 | Value                                   | File      |
| ------------------------- | --------------------------------------- | --------- |
| `fee_rate`                | 0.12                                    | config.py |
| `currency`                | INR                                     | config.py |
| `clip_model`              | `clip-ViT-B-32`                         | config.py |
| `min_interval_frac`       | 0.03                                    | config.py |
| `mlp_epochs`              | 150                                     | config.py |
| `mlp_batch_size`          | 512                                     | config.py |
| `mlp_lr`                  | 2e-3 (cosine schedule)                  | config.py |
| `mlp_dropout`             | 0.1                                     | config.py |
| `mlp_hidden`              | 256 (×2 layers)                         | config.py |
| `mlp_k`                   | 16 periodic freqs/feature               | config.py |
| `synth_n`                 | 30,000 rows                             | config.py |
| quantiles                 | (0.1, 0.5, 0.9)                         | model.py  |
| conformal target coverage | 0.80                                    | model.py  |
| calibration split         | 15%                                     | model.py  |
| `brand_multipliers`       | premium 1.2 / standard 1.0 / value 0.85 | config.py |
| condition prompts (CLIP)  | 5 prompts, scores 30–95                 | config.py |

### Test Coverage: 44 green + 1 gated eval (~15s suite)

### Running Module 5

```bash
cd Module-5
pip install -r requirements.txt
python -m p2p.train          # generate synthetic data + train model
uvicorn p2p.main:app --reload --port 8003

python -m p2p.eval           # reproduce held-out eval (P2P_RUN_EVAL=1 for full)
P2P_WARM_CLIP=1 uvicorn ...  # pre-warm CLIP at startup
```

### Deferred / Future Work

- **Geo-filtered buyer matching** (reuse Module 2's `retrieve()` with distance filter) — the original Module 5 core, deferred to post-hackathon
- Escrow/payments, real logistics
- Multimodal pricing (CLIP/SigLIP image + text embeddings into MLP input)
- Real P2P data (one MerRec shard) — drop-in for `synth.generate_xy`

---

## Full Tech Stack

| Layer                         | Technology                                    | Notes                                                                                                                               |
| ----------------------------- | --------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| **Frontend**                  | React                                         | Return flow Q&A, Health Card display, P2P divert offer, Green Coin wallet, Rec feed, P2P listing. No build step for Module 4 (CDN). |
| **Backend**                   | FastAPI (Python)                              | One service per module. Async throughout (`asyncio.to_thread` for heavy compute).                                                   |
| **AI — Anomaly**              | `anomalib` PatchCore/FastFlow                 | Unsupervised, defect-free images only. Shared grader workhorse.                                                                     |
| **AI — Wear Detection**       | Custom CV layer                               | Sole wear, fabric stress, stain detection on submitted images                                                                       |
| **AI — Condition (Option A)** | Qwen2.5-VL-7B (4-bit quantized)               | Local VLM, video-capable, GPU required                                                                                              |
| **AI — Condition (Option B)** | scikit-learn logreg + template                | CPU-fine, sub-2s, recommended default                                                                                               |
| **AI — Defect typing**        | YOLOv9 / ViT (optional)                       | Needs labeled defect dataset                                                                                                        |
| **AI — Recommend**            | `gte-modernbert-base` + `Qwen3-Reranker-0.6B` | Local, no API                                                                                                                       |
| **AI — P2P Condition**        | CLIP `ViT-B/32` zero-shot                     | Local, no labels                                                                                                                    |
| **AI — P2P Pricing**          | Neural quantile-MLP                           | Post-2023, ensemble-free, CQR calibration                                                                                           |
| **AI — Return Prevention**    | LightGBM                                      | AUC-ROC 0.9790, <300ms inference                                                                                                    |
| **Storage (demo)**            | SQLite + local filesystem                     | One DB per module                                                                                                                   |
| **Storage (production)**      | Postgres + S3                                 | ORM unchanged, connection string swap                                                                                               |
| **GPU requirement**           | G-series AWS instance                         | Option A only — all other modules CPU-only                                                                                          |

---

## Suggested Demo Build Order

1. **Module 1 end-to-end** — return flow (Q&A + image + video) → Social Connect fraud check (parallel) → local grader → Health Card → fraud branch (P2P offer) or normal routing → disposition. Tells the whole story, shows real AI, hits the <2s target, demonstrates wardrobing fraud catch. _Build first, protect at all costs._
2. **Module 5 P2P** — small surface area, directly answers Rahul persona, strong narrative payoff.
3. **Module 4 Green Coin** — easy bolt-on, very visual, owns the sustainability theme.
4. **Module 2 Recommend** — shows Renewed supply finding buyers (closes the loop).
5. **Module 3 Return Prevention** — strongest upstream-prevention closer if time remains.

### Wardrobing fraud catch moment

1. Customer submits Clothing & Footwear return — claims "never worn"
2. Social Connect scan (run in parallel with grader): finds Instagram story from 3 days ago featuring the item at a wedding → fraud_confidence: 0.91
3. Non-accusatory offer screen: "Would you like to resell this instead? Earn Green Credits + partial refund"
4. Customer chooses P2P → item enters Module 5 with `source: "p2p_fraud_divert"`
5. Fraudulent return converted to sustainable resale — Amazon recovers value, customer earns credits, item gets second life

### Small Seller moment (secondary beat)

After 200 auto-graded returns: seller dashboard shows `4,200 kg CO₂e avoided · equivalent to 5,060 trees`. Same seller who needed AI logistics now has an ESG number to show investors.

---

## Metrics to Pitch

- Recovery rate per returned item (target +20–30%) — directly counters "written off"
- % returns skipping physical inspection — local video grading removes manual inspection (Small Seller persona)
- Return-rate reduction from Module 3 prevention
- CO₂e avoided per quarter
- Renewed GMV growth
- Wardrobing fraud detection rate (new — Module 1 fraud layer)

---

## Production Roadmap

| Upgrade                                  | One-sentence pitch                                                                                                                                                                                          |
| ---------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **EU Digital Product Passport (DPP)**    | ESPR regulation mandates product lifecycle data for textiles and electronics by 2027 — our Health Card + Green Coin ledger _is_ a DPP-ready data model, giving Amazon early compliance infrastructure       |
| **India GCP integration**                | Link Green Coin to India's Government Green Credit Programme (LiFE initiative) so customers' eco-actions count toward the national tradable credit registry — a unique regulatory moat for Amazon India     |
| **Real LCA data (ecoinvent / Ecochain)** | Replace our lookup table with ISO 14083-compliant per-SKU emission factors — turns Green Coin into a credible carbon accounting system, not just a loyalty program                                          |
| **LinUCB bandit for re-ranking**         | Replace static `renewed_boost_weight` with a market-aware contextual bandit that learns the optimal boost from realized sales — the jump from competent recommender to the project's differentiating thesis |
| **Multimodal P2P pricing**               | CLIP/SigLIP image + text embeddings concatenated into the MLP input so price is learned from the photo, not just a condition scalar                                                                         |
| **Geo-filtered P2P buyer matching**      | Reuse Module 2's `retrieve()` with a distance filter to connect Rahul to the 50 nearby parents — the original Module 5 core                                                                                 |
| **Dynamic CO₂e routing**                 | Factor CO₂e cost alongside ₹ logistics cost in the disposition gate — a nearby P2P buyer saving 71 kg CO₂e should be preferred over FC resell even at slightly lower ₹ recovery                             |
| **Seller-side Green Coin**               | Reward sellers for low-return-rate SKUs upstream — closes the prevention loop before items enter the returns flow                                                                                           |
| **EmbeddingGemma-300m**                  | `google/embeddinggemma-300m` (Sep 2025, gated on HF) as the embedder upgrade once auth available                                                                                                            |

---

## Demo-to-Production Gaps

- Local grader → larger fine-tuned VLM + confidence calibration; low-confidence items fall back to human inspection
- Routing thresholds (90/70/50) are starting heuristics; production learns them from realized recovery value — a **delayed-reward decision problem**, not a static classifier (bandit/RL upgrade)
- Cost/CO₂e tables → real logistics + LCA data
- Social Connect → real OAuth connectors, data-minimization, retention controls, on-device processing
- P2P buyer matching → geo-filtered Module 2 embeddings (deferred)
- SQLite → Postgres; local storage → S3
- Synthetic training data → real datasets across all modules

---

## Test Coverage Summary

| Module                       | Tests                                      | Status                               |
| ---------------------------- | ------------------------------------------ | ------------------------------------ |
| Module 1 — Grading & Fraud   | 427                                        | ✅ ~3 seconds                        |
| Module 2 — Recommend         | 108                                        | ✅ (90 base + 15 social + Phase 2.1) |
| Module 3 — Return Prevention | Full suite (unit + property + integration) | ✅                                   |
| Module 4 — Green Coin        | 28                                         | ✅                                   |
| Module 5 — P2P Exchange      | 44 + 1 gated eval                          | ✅ ~15 seconds                       |
