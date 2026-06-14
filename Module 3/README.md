# Module 3 — Return Prevention: Technical Documentation

## 1. Overview

Module 3 adds an **AI-powered pre-purchase intervention layer** to the Second Life Commerce platform. It predicts the likelihood that a customer will return a product _before_ they complete checkout and shows targeted guidance on the Product Detail Page (PDP) — size nudges, social proof, comparison tools, or clarifying Q&A — to reduce avoidable returns.

**Key metrics:**

- Risk scoring in under 300ms (LightGBM inference)
- AUC-ROC: 0.9790 on validation set
- Zero external API calls — fully local compute

---

## 2. Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│                           Browser (React)                                   │
│                                                                            │
│   ┌──────────────────────┐    ┌─────────────────────┐                      │
│   │  Product Detail Page │──▶│    PDP Banner        │                      │
│   │  (useDwellTimer)     │    │  (intervention copy) │                      │
│   └──────────┬───────────┘    └─────────────────────┘                      │
│              │                                                              │
│   "Add to Cart" / "Buy Now" click                                          │
│   + page_dwell_seconds + is_buy_now                                        │
└──────────────┼─────────────────────────────────────────────────────────────┘
               │
               ▼
┌────────────────────────────────────────────────────────────────────────────┐
│              Module 3 — Return Prevention Service (FastAPI)                 │
│                                                                            │
│   POST /api/v1/risk-score                                                  │
│        │                                                                   │
│        ├──▶ Feature Assembler (9 features)                                 │
│        │         │                                                         │
│        │         ├── Category Taxonomy (in-memory, loaded at startup)       │
│        │         ├── Customer Profile Client (Module 2, read-only)          │
│        │         ├── Price Band Profile (local DB)                          │
│        │         └── Seller Profile (local DB)                              │
│        │                                                                   │
│        ├──▶ Risk Scorer (LightGBM predict_proba)                           │
│        │                                                                   │
│        ├──▶ Intervention Generator (template strings)                      │
│        │                                                                   │
│        └──▶ Green Coin Emitter (async, non-blocking → Module 4)            │
│                                                                            │
│   GET  /api/v1/fit-profile/{customer_id}                                   │
│   POST /api/v1/model/reload  (internal only)                               │
│   GET  /api/v1/model/feature-importance                                    │
└────────────────────────────────────────────────────────────────────────────┘
               │                                    │
               ▼                                    ▼
┌──────────────────────────┐         ┌──────────────────────────┐
│ Module 2 — Recommend     │         │ Module 4 — Green Coin    │
│ (Customer_Profile store) │         │ (purchase_avoidance evt) │
│ READ-ONLY                │         │ Async, with retry        │
└──────────────────────────┘         └──────────────────────────┘
```

---

## 3. ML Model

### Model Type

**LightGBM Binary Classifier** — predicts P(return | features)

### Feature Vector (9 features, assembled at checkout-click time)

| #   | Feature                          | Type  | Source                         | Fallback            |
| --- | -------------------------------- | ----- | ------------------------------ | ------------------- |
| 1   | `category_return_rate`           | float | Category Taxonomy              | Global default 0.20 |
| 2   | `user_category_return_rate`      | float | Customer order history         | Category mean       |
| 3   | `in_user_high_return_price_band` | bool  | Price Band Profile             | `false`             |
| 4   | `has_size_ambiguity`             | bool  | Category Taxonomy              | `false`             |
| 5   | `page_dwell_seconds`             | float | Client-side (PDP load → click) | Required field      |
| 6   | `is_buy_now`                     | bool  | Which button user clicked      | Required field      |
| 7   | `product_review_rating`          | float | Product catalog                | 3.5                 |
| 8   | `seller_return_rate`             | float | Seller Profile table           | Global mean         |
| 9   | `is_sale_active`                 | bool  | Promotions flag                | `false`             |

### Training Details

- **Training data**: 10,000 synthetic samples (script: `ml/synthesize_dataset.py`)
- **Split**: 80/20 stratified
- **Hyperparameters**: 300 estimators, learning_rate=0.05, max_depth=6, num_leaves=31
- **Validation AUC-ROC**: 0.9790
- **Validation Log-loss**: 0.1178

### Feature Importance (from trained model)

| Feature                        | Gain Score |
| ------------------------------ | ---------- |
| product_review_rating          | 1781       |
| user_category_return_rate      | 1754       |
| category_return_rate           | 1413       |
| page_dwell_seconds             | 1281       |
| seller_return_rate             | 1251       |
| in_user_high_return_price_band | 362        |
| is_buy_now                     | 330        |
| has_size_ambiguity             | 307        |
| is_sale_active                 | 258        |

### Model Files

- Trained model: `ml/models/lgbm_return_risk.pkl`
- Training script: `ml/train.py`
- Dataset synthesis: `ml/synthesize_dataset.py`
- Training report: `ml/models/training_report.json`

---

## 4. API Endpoints

### POST /api/v1/risk-score

Compute return-risk probability and generate intervention.

**Request:**

```json
{
  "customer_id": "CUST-001",
  "product_id": "Women's Shoes",
  "page_dwell_seconds": 45.2,
  "is_buy_now": false,
  "seller_id": "SELLER-042",
  "product_price": 1299.0,
  "is_sale_active": true
}
```

**Important implementation note:** In this prototype, `product_id` maps directly to a **subcategory key** in the taxonomy. For example, `"Women's Shoes"` is looked up in `data/taxonomy.json` to retrieve `category_return_rate` and `has_size_ambiguity`. In production, this would be resolved through a product catalog service.

**Optional fields:**

- `seller_id` — if omitted, global mean seller return rate is used
- `product_price` — if omitted, `in_user_high_return_price_band` defaults to `false`
- `is_sale_active` — defaults to `false`
- `product_review_rating` (float, 1.0–5.0) — if omitted, defaults to 3.5

**Response (200):**

```json
{
  "risk_score": 0.82,
  "intervention_type": "SIZE_GUIDANCE",
  "intervention_copy": "Heads up: your kept size in Nike is 9. Most returns from Nike are in size 10.",
  "taxonomy_miss": false
}
```

**Error Codes:**

- 422: Missing required field (`customer_id`, `product_id`, `page_dwell_seconds`, `is_buy_now`)
- 503: Internal dependency failure

### GET /api/v1/fit-profile/{customer_id}

Returns the customer's fit profile grouped by brand.

**Response (200):**

```json
{
  "Nike": [
    {
      "order_id": "ORD-001",
      "purchased_size": "9",
      "status": "kept",
      "return_reason": null
    },
    {
      "order_id": "ORD-007",
      "purchased_size": "10",
      "status": "returned",
      "return_reason": "too large"
    }
  ]
}
```

Returns `{}` with HTTP 200 when no fit profile exists.

### POST /api/v1/model/reload (Internal Only)

Hot-swap the model without restarting the service.

**Response (200):**

```json
{
  "status": "reloaded",
  "model_path": "ml/models/lgbm_return_risk.pkl",
  "file_mtime": "2026-06-14T10:30:00Z"
}
```

### GET /api/v1/model/feature-importance

Returns LightGBM gain-based feature importances for demo explainability.

**Response (200):**

```json
{
  "product_review_rating": 1781,
  "user_category_return_rate": 1754,
  "category_return_rate": 1413,
  "page_dwell_seconds": 1281,
  "seller_return_rate": 1251,
  "in_user_high_return_price_band": 362,
  "is_buy_now": 330,
  "has_size_ambiguity": 307,
  "is_sale_active": 258
}
```

---

## 5. Intervention System

### Risk Threshold

Default: **0.6** (configurable via `RISK_THRESHOLD` env var)

When `risk_score > 0.6`, an intervention fires.

### Intervention Types (Priority Order)

| Priority | Type               | Condition                                          |
| -------- | ------------------ | -------------------------------------------------- |
| 1        | `SIZE_GUIDANCE`    | Fit Profile exists for (customer, brand)           |
| 2        | `SOCIAL_PROOF`     | Subcategory has return data in taxonomy            |
| 3        | `COMPARISON_NUDGE` | Alternative in-stock product exists in subcategory |
| 4        | `CLARIFYING_QA`    | Always available (default fallback)                |

### Template Examples

**SIZE_GUIDANCE:**

> "Heads up: your kept size in {brand} is {kept_size}. Most returns from {brand} are in size {top_returned_size}."

**SOCIAL_PROOF:**

> "{return_rate_pct}% of buyers in {subcategory} return items — most commonly for '{top_reason}'."

**COMPARISON_NUDGE:**

> "Before you buy: {alt_product_name} has a {alt_return_rate_pct}% return rate vs {this_return_rate_pct}% for this item."

**CLARIFYING_QA:**

> Q: "Why do buyers return {subcategory} items?"
> A: "The most common reason is '{top_reason}'."

---

## 6. Database Schema

### Fit_Profile

```sql
CREATE TABLE fit_profile (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id      TEXT NOT NULL,
    brand            TEXT NOT NULL,
    order_id         TEXT NOT NULL UNIQUE,
    purchased_size   TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'pending',  -- pending | kept | returned
    return_reason    TEXT,
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at       DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Seller_Profile

```sql
CREATE TABLE seller_profile (
    seller_id    TEXT PRIMARY KEY,
    return_rate  REAL NOT NULL CHECK (return_rate >= 0.0 AND return_rate <= 1.0),
    total_orders INTEGER NOT NULL DEFAULT 0,
    total_returns INTEGER NOT NULL DEFAULT 0,
    updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Price_Band_Profile

```sql
CREATE TABLE price_band_profile (
    customer_id  TEXT NOT NULL,
    price_band   TEXT NOT NULL,  -- '0-500' | '501-2000' | '2001-10000' | '10000+'
    total_orders INTEGER NOT NULL DEFAULT 0,
    total_returns INTEGER NOT NULL DEFAULT 0,
    return_rate  REAL NOT NULL DEFAULT 0.0,
    updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (customer_id, price_band)
);
```

---

## 7. Integration Contracts

### Module 2 (Recommend) — Customer Profile [READ-ONLY]

**Consumed endpoint:** `GET {CUSTOMER_PROFILE_BASE_URL}/api/v2/customer-profile/{customer_id}`

**Default base URL:** `http://localhost:8001` (configurable via `CUSTOMER_PROFILE_BASE_URL` env var)

**Timeout:** 500ms (httpx async). On timeout or connection error → Module 3 falls back to category-level baselines and returns HTTP 200 (degraded accuracy, not 503).

**What Module 3 actually reads from the response:**

- `order_history[].subcategory` — to compute `user_category_return_rate`
- `order_history[].status` — filters by `"returned"` to count returns in the subcategory
- If fewer than 2 orders exist in the subcategory, `user_category_return_rate` defaults to `category_return_rate`

**Expected schema:**

```json
{
  "customer_id": "string",
  "order_history": [
    {
      "order_id": "string",
      "product_id": "string",
      "category": "string",
      "subcategory": "string",
      "brand": "string",
      "purchased_size": "string | null",
      "price": "float",
      "seller_id": "string",
      "status": "completed | returned | pending",
      "return_reason": "string | null",
      "order_date": "ISO-8601"
    }
  ]
}
```

**Fallback behavior when Module 2 is unavailable:**

- `user_category_return_rate` → uses `category_return_rate` from taxonomy
- Scoring still returns a valid HTTP 200 response

### Module 4 (Green Coin) — Purchase Avoidance Events [WRITE]

**Target endpoint:** `POST {GREEN_COIN_BASE_URL}/api/v4/purchase-avoidance`

**Default base URL:** `http://localhost:8002` (configurable via `GREEN_COIN_BASE_URL` env var)

**Event payload (actual Pydantic schema: `PurchaseAvoidanceEvent`):**

```json
{
  "event_type": "purchase_avoidance",
  "customer_id": "string",
  "product_id": "string",
  "risk_score": 0.82,
  "intervention_type": "SIZE_GUIDANCE",
  "session_id": "uuid",
  "emitted_at": "ISO-8601"
}
```

**Green Coin tiers (owned by Module 4):**

| Risk Score   | Coins |
| ------------ | ----- |
| [0.60, 0.75) | 10    |
| [0.75, 0.90) | 25    |
| [0.90, 1.00] | 50    |

**Delivery:** Async, non-blocking (FastAPI `BackgroundTask`). One retry after 60s. On second failure → appended as JSONL to `purchase_avoidance_retry.log`.

**Deduplication:** Module 3 guarantees at most one emission per `(customer_id, product_id, session_id)` tuple per session (in-memory set).

---

## 8. Critical Integration Notes for Other Modules

1. **Taxonomy keys = subcategory names.** In this prototype, `product_id` in the risk-score request is looked up directly as a subcategory key in `data/taxonomy.json`. Valid keys include: `"Women's Shoes"`, `"Men's Jeans"`, `"T-Shirts"`, `"Rings"`, `"Smartphones"`, `"Earphones"`, `"Tablets"`, `"Blenders"`, `"Coffee Makers"`, `"Novels"`, `"Textbooks"`.

2. **Global seller sentinel.** At startup, a `__global__` row is seeded in `seller_profile` with `return_rate=0.15`. This is used as the fallback when a seller_id is unknown.

3. **Module 3 never writes to Module 2's store.** All Fit_Profile, Seller_Profile, and Price_Band_Profile data lives in Module 3's own SQLite database (`return_prevention.db`).

4. **Module 4 must expose `POST /api/v4/purchase-avoidance`.** Module 3 will POST the `PurchaseAvoidanceEvent` JSON payload there. If Module 4 returns any non-2xx status, Module 3 retries once after 60s then logs to a local file.

5. **Module 2 must expose `GET /api/v2/customer-profile/{customer_id}`.** Module 3 calls this with a 500ms timeout. If it's not running, Module 3 degrades gracefully.

---

## 9. Frontend Components

```
src/components/
├── ProductDetailPage.tsx        # Root PDP, starts dwell timer
├── hooks/
│   ├── useDwellTimer.ts         # PDP load → checkout-click elapsed time
│   ├── useRiskScore.ts          # POST /api/v1/risk-score (non-blocking)
│   └── useBannerSession.ts      # sessionStorage for dismissed banners
└── PdpBanner/
    ├── PdpBanner.tsx            # Renders intervention + dismiss button
    ├── PdpBanner.module.css     # WCAG 2.1 AA compliant styles
    └── icons/
        ├── SizeGuidanceIcon.tsx
        ├── SocialProofIcon.tsx
        ├── ComparisonNudgeIcon.tsx
        └── ClarifyingQaIcon.tsx
```

**Key behaviors:**

- Dwell timer starts on PDP mount, reports elapsed seconds at checkout click
- Risk score request is **non-blocking** — checkout proceeds immediately
- Banner renders above "Add to Cart" button within 100ms of API response
- Banner dismissal stored in `sessionStorage` (cleared on tab close)
- 30-minute avoidance timer: if user doesn't add to cart → emits purchase_avoidance event

---

## 10. Project Structure

```
Module 3/
├── data/
│   └── taxonomy.json               # 11 subcategories, 5 categories
├── ml/
│   ├── data/
│   │   └── return_prevention_dataset.csv
│   ├── models/
│   │   ├── lgbm_return_risk.pkl    # Trained model
│   │   └── training_report.json    # AUC-ROC, log-loss, feature importance
│   ├── synthesize_dataset.py       # Generates 10K training samples
│   └── train.py                    # Trains LightGBM, saves .pkl + report
├── return_prevention/
│   ├── api/
│   │   ├── routes_risk.py          # POST /api/v1/risk-score
│   │   ├── routes_fit.py           # GET  /api/v1/fit-profile/{id}
│   │   └── routes_model.py         # POST /model/reload, GET /feature-importance
│   ├── core/
│   │   ├── feature_assembler.py    # 9-feature vector assembly + fallbacks
│   │   ├── intervention.py         # Type selection + template copy generation
│   │   ├── model_registry.py       # Singleton, thread-safe, hot-reload
│   │   └── scorer.py               # predict_proba wrapper + clamping
│   ├── db/
│   │   ├── database.py             # SQLAlchemy engine + session factory
│   │   ├── models.py               # ORM: FitProfile, SellerProfile, PriceBandProfile
│   │   └── repositories.py         # CRUD helpers for all 3 tables
│   ├── integrations/
│   │   ├── customer_profile.py     # httpx async client (Module 2, 500ms timeout)
│   │   └── green_coin.py           # Async event emitter (Module 4, retry logic)
│   ├── schemas/
│   │   ├── risk.py                 # RiskScoreRequest/Response, InterventionType enum
│   │   ├── fit.py                  # FitProfileEntry/Response
│   │   └── events.py              # PurchaseAvoidanceEvent
│   ├── tasks/
│   │   └── fit_profile_aging.py    # Background: pending → kept after 30 days
│   ├── taxonomy/
│   │   └── taxonomy_loader.py      # JSON → in-memory dict (startup validation)
│   ├── config.py                   # pydantic-settings (all env vars)
│   ├── main.py                     # FastAPI app factory + lifespan hooks
│   └── requirements.txt            # Pinned dependencies
├── src/components/                 # React frontend (PDP + Banner)
├── tests/                          # Unit + property-based tests
├── package.json                    # Frontend dependencies
├── pytest.ini                      # Test configuration
└── tsconfig.json                   # TypeScript configuration
```

---

## 11. Running the Service

```bash
cd "Module 3"

# Install Python dependencies
pip install -r return_prevention/requirements.txt

# Train the model (already done — skip if ml/models/lgbm_return_risk.pkl exists)
python ml/synthesize_dataset.py
python ml/train.py

# Start the service
uvicorn return_prevention.main:app --reload --port 8000
```

**Environment variables (all optional, have defaults):**

```env
MODEL_PATH=ml/models/lgbm_return_risk.pkl
RISK_THRESHOLD=0.6
DB_URL=sqlite:///./return_prevention.db
TAXONOMY_PATH=data/taxonomy.json
CUSTOMER_PROFILE_BASE_URL=http://localhost:8001
GREEN_COIN_BASE_URL=http://localhost:8002
```

---

## 12. Error Handling Summary

| Scenario                              | Behavior                                  | HTTP      |
| ------------------------------------- | ----------------------------------------- | --------- |
| Model file missing at startup         | Refuse to start                           | —         |
| Taxonomy file missing at startup      | Refuse to start                           | —         |
| Customer Profile unreachable (>500ms) | Use category baseline; proceed            | 200       |
| Unknown seller                        | Use global mean                           | 200       |
| Product not in taxonomy               | Return risk_score=0.0, taxonomy_miss=true | 200       |
| Missing required field                | Pydantic validation error                 | 422       |
| DB failure during scoring             | Service unavailable                       | 503       |
| Green Coin Service down               | Log + retry after 60s                     | — (async) |
| Invalid RISK_THRESHOLD env var        | Retain default 0.6; log error             | —         |

---

## 13. Testing

```bash
# Run all tests
pytest

# Run only property-based tests
pytest tests/property/

# Run specific test module
pytest tests/test_feature_assembler.py -v
```

**Test coverage:**

- Unit tests: repositories, taxonomy loader, model registry, feature assembler, scorer, intervention generator, API routes
- Property-based tests (Hypothesis): 16 correctness properties covering all acceptance criteria
- Integration tests: end-to-end scoring with real DB, Customer Profile fallback, Green Coin retry behavior
