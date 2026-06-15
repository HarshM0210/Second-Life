# Module 1 — Grading, Fraud Detection & Quality System

## Integration Guide

This document is the source of truth for integrating with Module 1. All data contracts, API shapes, and behaviors described here are verified against the actual implementation.

---

## What Module 1 Produces

Module 1's sole output to downstream modules is the **Health Card JSON**, stored in the `health_cards` SQLite table and returned via the REST API. Any module that needs grading/disposition data should read from this contract.

---

## Health Card JSON — The Inter-Module Contract

This is the **exact** Pydantic-validated schema produced by Module 1. Every field is guaranteed present on every successful pipeline execution.

```python
# From: backend/app/models/health_card.py

class HealthCard(BaseModel):
    condition: Literal["Excellent", "Good", "Fair", "Poor"]
    health_score: int  # 0–100 (Field(ge=0, le=100))
    confidence: float  # 0.0–1.0 (Field(ge=0.0, le=1.0))
    warranty_left_months: int  # >= 0 (Field(ge=0))
    defects: list[str]
    anomaly_heatmap_uri: str
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
    fraud_confidence: float  # 0.0–1.0 (Field(ge=0.0, le=1.0))
    p2p_offered: bool
    customer_chose_p2p: bool
```

### Example Health Card JSON

```json
{
  "condition": "Good",
  "health_score": 78,
  "confidence": 1.0,
  "warranty_left_months": 5,
  "defects": ["sole_wear", "stains"],
  "anomaly_heatmap_uri": "s3://second-life/heatmaps/electronics_a1b2c3d4e5f6_heatmap.png",
  "justification": "Good. Detected: sole_wear, stains. Minor anomalies detected. Functional check: pass. Warranty: 5 months remaining.",
  "disposition": "refurbish",
  "source": "standard_return",
  "fraud_signal": {
    "social_scan_performed": false,
    "product_found_in_social": false,
    "fraud_confidence": 0.12,
    "p2p_offered": false,
    "customer_chose_p2p": false
  }
}
```

### Schema Rules

- **Append-only**: Fields are never removed or renamed. New fields may be added as optional.
- **Types are immutable**: `health_score` will always be `int`, `confidence` will always be `float`, etc.
- **All fields are always present**: No field is ever omitted. If data is unavailable, safe defaults are used (e.g., empty `defects: []`, `confidence: 0.7`).

### Important Notes for Integration

1. **`disposition` is the routing decision**. Downstream modules should use this to determine where the item goes.
2. **`source` indicates the return path**: `"standard_return"` means normal flow; `"p2p_fraud_divert"` means the customer opted for P2P resale.
3. **After P2P choice**, the Health Card is mutated in the DB. The `/p2p-choice` endpoint adds a `"flags"` array (not in the Pydantic schema) dynamically:
   - If `chose_p2p=false`: `health_card_data["flags"] = ["enhanced_inspection"]` is added to the raw JSON
   - This field is **not** Pydantic-validated — read it as optional from the JSON blob
4. **`confidence`** reflects pipeline component availability: `1.0` = all components succeeded, `0.7` = anomaly model was unavailable.
5. **`anomaly_heatmap_uri`** may be an empty string `""` if the anomaly detector failed or timed out.

---

## REST API

Base URL: `http://localhost:8000` (dev)

All endpoints are under the prefix `/api/returns`.

### POST /api/returns/initiate

Validates the return window and returns category-specific Q&A questions.

#### Request

```json
{
  "order_id": "ORD-123456",
  "product_id": "PROD-789",
  "customer_id": "CUST-001",
  "delivery_date": "2026-05-01", // OPTIONAL — ISO date, defaults to 7 days ago
  "category": "Electronics" // OPTIONAL — defaults to "Electronics"
}
```

> **Note**: `delivery_date` and `category` are optional demo/testing overrides. In production, these would be looked up from an orders service. The current implementation uses a mock lookup.

#### Response — 200 (Eligible)

```json
{
  "return_id": "RET-a1b2c3d4e5f6",
  "eligible": true,
  "window_days": 30,
  "days_elapsed": 12,
  "category": "Electronics",
  "questions": [
    {
      "id": "return_reason",
      "text": "What is the reason for your return?",
      "options": ["Item is defective / not working", "Item not as described in listing", ...],
      "supplementary_input": null,
      "conditional_display": null
    },
    {
      "id": "accessories",
      "text": "Are all original accessories included?",
      "options": ["Yes — all accessories present", "Some accessories missing (specify below)", ...],
      "supplementary_input": {"type": "text_field", "max_length": 200},
      "conditional_display": null
    }
  ]
}
```

#### Response — 403 (Window Expired)

```json
{
  "detail": {
    "return_id": null,
    "eligible": false,
    "message": "Return window expired on 2026-06-01. Returns must be initiated within 30 days of delivery.",
    "expiry_date": "2026-06-01"
  }
}
```

> **Note**: The 403 response wraps the body in `detail` (FastAPI's HTTPException format).

#### Response — 500 (Service Error)

```json
{
  "detail": "Return eligibility could not be verified. Please retry."
}
```

---

### POST /api/returns/{return_id}/submit

Submits Q&A answers and media URIs, triggers the full grading pipeline, returns the Health Card.

#### Request

```json
{
  "qa_answers": {
    "return_reason": "Item is defective / not working",
    "functional_status": "Not functional — does not power on / completely broken",
    "physical_condition": "Minor cosmetic damage (light scratches, small dents)",
    "accessories": "Yes — all accessories present",
    "original_packaging": "Yes — original box with all inserts",
    "ownership_duration": "Used briefly (less than a week)",
    "factory_reset": "Yes — fully reset, personal data removed",
    "liquid_damage": "No — never exposed to liquid or impact"
  },
  "image_uris": ["s3://uploads/img1.jpg", "s3://uploads/img2.jpg"],
  "video_frame_uris": [
    "s3://uploads/frame1.jpg",
    "s3://uploads/frame2.jpg",
    "s3://uploads/frame3.jpg",
    "s3://uploads/frame4.jpg",
    "s3://uploads/frame5.jpg"
  ],
  "catalog_metadata": {
    "category": "Electronics",
    "original_price": 24999.0,
    "purchase_date": "2026-05-01",
    "warranty_remaining_months": 5
  }
}
```

**Constraints:**

- `image_uris`: 1–5 items required
- `video_frame_uris`: optional (default empty list)
- `catalog_metadata.original_price`: must be > 0
- `catalog_metadata.warranty_remaining_months`: must be >= 0

#### Response — 200 (Success)

```json
{
  "health_card": {
    "condition": "Good",
    "health_score": 78,
    "confidence": 1.0,
    "warranty_left_months": 5,
    "defects": ["sole_wear"],
    "anomaly_heatmap_uri": "s3://second-life/heatmaps/electronics_abc123_heatmap.png",
    "justification": "Good. Detected: sole_wear. Minor anomalies detected. Functional check: pass. Warranty: 5 months remaining.",
    "disposition": "refurbish",
    "source": "standard_return",
    "fraud_signal": {
      "social_scan_performed": false,
      "product_found_in_social": false,
      "fraud_confidence": 0.08,
      "p2p_offered": false,
      "customer_chose_p2p": false
    }
  },
  "p2p_divert_offered": false
}
```

**`p2p_divert_offered` is `true` when:**

- `fraud_signal.fraud_confidence >= 0.60` AND
- `catalog_metadata.category == "Clothing & Footwear"`

#### Response — 400 (Validation Error)

```json
{
  "detail": {
    "message": "Incomplete Q&A answers",
    "missing_question_ids": ["factory_reset", "liquid_damage"]
  }
}
```

#### Response — 404

```json
{
  "detail": "Return session 'RET-xxx' not found"
}
```

#### Response — 500 (Pipeline Failure)

```json
{
  "detail": {
    "message": "Grading could not be completed: all grader components failed.",
    "failed_component": "grader"
  }
}
```

---

### POST /api/returns/{return_id}/p2p-choice

Records the customer's P2P marketplace choice and updates the persisted Health Card.

#### Request

```json
{
  "chose_p2p": true
}
```

#### Response — 200

```json
{
  "health_card": {
    "condition": "Good",
    "health_score": 80,
    "confidence": 0.9,
    ...
    "source": "p2p_fraud_divert",
    "fraud_signal": {
      "social_scan_performed": true,
      "product_found_in_social": true,
      "fraud_confidence": 0.75,
      "p2p_offered": true,
      "customer_chose_p2p": true
    }
  }
}
```

**Behavior:**

- `chose_p2p=true`: sets `source="p2p_fraud_divert"`, `fraud_signal.p2p_offered=true`, `fraud_signal.customer_chose_p2p=true`
- `chose_p2p=false`: keeps `source="standard_return"`, sets `fraud_signal.p2p_offered=true`, `fraud_signal.customer_chose_p2p=false`, adds `"flags": ["enhanced_inspection"]` to the Health Card JSON

---

### GET /health

```json
{ "status": "ok", "module": "grading-fraud-quality" }
```

---

## SQLite Database Schema

Database file: `second_life.db` (configurable via `DATABASE_PATH` env var). Auto-initialized on first startup.

### `returns` table

| Column        | Type          | Description                                     |
| ------------- | ------------- | ----------------------------------------------- |
| id            | TEXT PK       | Return ID (e.g., "RET-a1b2c3d4e5f6")            |
| order_id      | TEXT NOT NULL | Original order ID                               |
| product_id    | TEXT NOT NULL | Product identifier                              |
| customer_id   | TEXT NOT NULL | Customer identifier                             |
| category      | TEXT NOT NULL | Product category                                |
| delivery_date | TEXT NOT NULL | ISO 8601 date                                   |
| initiated_at  | TEXT NOT NULL | ISO 8601 datetime                               |
| status        | TEXT NOT NULL | `initiated` → `grading` → `complete` or `error` |
| qa_answers    | TEXT          | JSON blob (nullable)                            |
| media_uris    | TEXT          | JSON array (nullable)                           |
| created_at    | TEXT          | Auto-set to `datetime('now')`                   |

### `health_cards` table

| Column           | Type             | Description                     |
| ---------------- | ---------------- | ------------------------------- |
| id               | TEXT PK          | Health Card UUID                |
| return_id        | TEXT NOT NULL FK | References `returns.id`         |
| health_card_json | TEXT NOT NULL    | Full Health Card as JSON string |
| created_at       | TEXT             | Auto-set to `datetime('now')`   |

**To read a Health Card for a return**: `SELECT health_card_json FROM health_cards WHERE return_id = ?`

### `cost_lookup` table

| Column                | Type                           |
| --------------------- | ------------------------------ |
| category              | TEXT PK                        |
| reverse_logistics     | REAL                           |
| inspection            | REAL                           |
| refurbishment         | REAL                           |
| storage               | REAL                           |
| total_processing_cost | REAL (generated, sum of above) |

### `category_weights` table

| Column     | Type                |
| ---------- | ------------------- |
| category   | TEXT PK             |
| w1_anomaly | REAL (default 30.0) |
| w2_defect  | REAL (default 25.0) |
| w3_reason  | REAL (default 20.0) |
| w4_wear    | REAL (default 25.0) |

### `return_windows` table

| Column      | Type                 |
| ----------- | -------------------- |
| category    | TEXT PK              |
| window_days | INTEGER (default 30) |

---

## Seeded Configuration Data

### Return Windows

| Category            |     Window (days)     |
| ------------------- | :-------------------: |
| Food & Grocery      |           7           |
| Electronics         |          30           |
| Clothing & Footwear |          15           |
| Other               |          30           |
| Unknown/missing     | 30 (default fallback) |

### Category Weights (Health Score Formula)

Formula: `health_score = clamp(100 - (w1×anomaly + w2×defect + w3×reason + w4×wear), 0, 100)`

| Category            | w1 (anomaly) | w2 (defect) | w3 (reason) | w4 (wear) |
| ------------------- | :----------: | :---------: | :---------: | :-------: |
| Food & Grocery      |     20.0     |    30.0     |    30.0     |   20.0    |
| Electronics         |     30.0     |    25.0     |    25.0     |   20.0    |
| Clothing & Footwear |     20.0     |    20.0     |    20.0     |   40.0    |
| Other               |     25.0     |    25.0     |    25.0     |   25.0    |

### Cost Lookup (Gate A — Economics)

| Category            | Reverse Logistics | Inspection | Refurbishment | Storage | **Total** |
| ------------------- | :---------------: | :--------: | :-----------: | :-----: | :-------: |
| Food & Grocery      |       50.0        |    20.0    |     10.0      |  15.0   | **95.0**  |
| Electronics         |       200.0       |   150.0    |     300.0     |  100.0  | **750.0** |
| Clothing & Footwear |       80.0        |    50.0    |     60.0      |  30.0   | **220.0** |
| Other               |       100.0       |    75.0    |     100.0     |  50.0   | **325.0** |

---

## Disposition Routing Logic

Priority order (first match wins):

| Priority | Rule                            | Disposition           | `gate_applied`      | Conditions                                                                                                                                           |
| :------: | ------------------------------- | --------------------- | ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
|    1     | Safety override                 | `manual_review`       | `safety_hold`       | Q&A: safety_concern = "Yes — I believe this item is unsafe" OR "Minor concern (describe in notes)" OR liquid_damage = "Significant liquid damage..." |
|    2     | Food & Grocery: broken/consumed | `recycle`             | `category_override` | seal_integrity broken OR quantity partially/mostly consumed                                                                                          |
|    2     | Food & Grocery: expired         | `recycle`             | `category_override` | expiry_date < today                                                                                                                                  |
|    2     | Food & Grocery: wrong item      | `return_to_seller`    | `category_override` | sealed + unexpired + reason = "Wrong item delivered"                                                                                                 |
|    3     | Electronics: unreset            | `manual_review`       | `safety_hold`       | factory_reset = "No — personal data still on device"                                                                                                 |
|    4     | Hygiene (Other): skin contact   | `donate` or `recycle` | `category_override` | skin_contact = "Yes — and it HAS been used on skin / body"; donate if score > 50, recycle otherwise                                                  |
|    5     | Gate A: economics               | `return_to_seller`    | `A`                 | total_processing_cost < product_value                                                                                                                |
|    5     | Gate A: unknown category        | `manual_review`       | `A`                 | category not in cost_lookup table                                                                                                                    |
|    6     | Gate B: score > 90              | `resell`              | `B`                 | —                                                                                                                                                    |
|    6     | Gate B: score > 70 (Electronics) | `refurbish`          | `B`                 | Electronics only                                                                                                                                     |
|    6     | Gate B: score > 50              | `donate`              | `B`                 | —                                                                                                                                                    |
|    6     | Gate B: score ≤ 50              | `recycle`             | `B`                 | —                                                                                                                                                    |
|    6     | Gate B: score unavailable       | `recycle`             | `B`                 | flag: `health_score_unavailable`                                                                                                                     |

---

## Pipeline Execution Flow

```
PipelineInput
    │
    ├─── asyncio.gather ──────────────────────────────────┐
    │                                                      │
    │   Grader (asyncio.gather):                          │   Fraud Scanner:
    │   ├── Anomaly Detector (timeout 5s)                 │   └── scan() (timeout 5s)
    │   ├── Wear Detector (timeout 5s)                    │       Only if category ==
    │   └── Intent Classifier (timeout 5s)                │       "Clothing & Footwear"
    │                                                      │
    └──────────────────────────────────────────────────────┘
    │
    ▼
Cross-Validation: authoritative_penalty = max(intent_penalty, wear_penalty)
    │
    ▼
Health Score Computer: 100 - (w1×anomaly + w2×defect + w3×reason + w4×authoritative_wear)
    │
    ▼
Justification Engine: template rendering
    │
    ▼
Fraud Aggregation: weighted_sum(social_signal, wear_penalty, behavioural_score)
    │                 + fraud escalation if "never used" + wear > 0
    │
    ▼
Disposition Router: priority chain → disposition
    │
    ▼
Health Card Assembler → HealthCard
```

**Total budget**: 2000ms. **Component hard timeout**: 5000ms each.

---

## Grading Pipeline & Anomaly Backends

Three components run concurrently via `asyncio.gather`. A local computer vision pipeline inspects submitted images for **anomalies, defects, and wear patterns**, while a structured Q&A flow captures the customer's self-reported condition. Both run in parallel and their results are combined to produce the final health score:

```
health_score = 100 − (w1·anomaly_severity + w2·defect_penalty + w3·return_reason_penalty + w4·wear_detection_penalty)
```

A **cross-validation layer** takes `max(intent_penalty, wear_penalty)` as the authoritative wear signal, ensuring that self-serving Q&A answers cannot override physical evidence from the CV pipeline. **Total pipeline budget: 2000ms.**

### Anomaly Detector Backends

The anomaly detector supports two backends, selected via the `ANOMALY_BACKEND` environment variable:

| Backend            | Description                                                                                              |
| ------------------ | ------------------------------------------------------------------------------------------------------- |
| `heuristic` (default) | Classical OpenCV severity estimate. Always available, zero dependencies.                             |
| `dinov2` (opt-in)  | Cutting-edge, **training-free** DINOv2 backend (**ViT-S/14 with registers**) that compares image patch features against a per-category **"known-good" memory bank**. |

When `dinov2` is enabled, it **ensembles pessimistically** with the OpenCV heuristic:

```
final_severity = max(model_severity, heuristic_severity)
```

The DINOv2 backend is **opt-in** (`ANOMALY_BACKEND=dinov2`) and **gracefully falls back** to the heuristic when `torch`/weights are unavailable, so the pipeline never crashes. Per-category reference ("known-good") images are stored under `storage/dinov2/refs/<category>/`.

### Condition Routing Gate

Once the score is computed, it is routed through the Condition Routing gate:

- Score **above 90** → `resell`
- Score **above 70** → `refurbish` (**Electronics only**)
- Score **above 50** → `donate`
- Score **50 or below** → `recycle`

---

## Error Handling & Graceful Degradation

| Component Failure              | Fallback Behavior                                    | Effect on Health Card                                        |
| ------------------------------ | ---------------------------------------------------- | ------------------------------------------------------------ |
| Anomaly model not found        | severity=0.0, model_available=false                  | confidence=0.7, defects includes "anomaly_model_unavailable" |
| Anomaly detector crash/timeout | severity=1.0 (worst case)                            | Low health score, defects includes failure reason            |
| Wear detector failure          | penalty=0.0, analysis_performed=false                | No wear contribution to score                                |
| Intent classifier failure      | penalty=0.15 (medium default), unclassified=true     | Medium penalty applied                                       |
| Fraud scanner failure          | social_scan_performed=false                          | fraud_confidence from wear+behavioural only                  |
| All 3 grader components fail   | **PipelineError returned** (no Health Card produced) | API returns HTTP 500                                         |
| Pipeline exceeds 2s budget     | Warning logged, result still returned                | No effect on output                                          |

---

## Return Status Lifecycle

```
initiated  →  grading  →  complete
                       →  error (if pipeline fails)
```

---

## Product Categories

The system supports exactly 4 categories:

1. **Food & Grocery** — 6 Q&A questions, 7-day return window
2. **Electronics** — 8 Q&A questions, 30-day return window
3. **Clothing & Footwear** — 8 Q&A questions, 15-day return window, fraud scan eligible
4. **Other** — 8 Q&A questions, 30-day return window

Only **Clothing & Footwear** triggers the Social Connect fraud scanner and P2P divert path.

---

## How to Read Health Cards from the Database

For downstream modules that need to consume Health Cards directly from SQLite:

```python
import aiosqlite
import json

async def get_health_card(return_id: str) -> dict | None:
    async with aiosqlite.connect("second_life.db") as db:
        cursor = await db.execute(
            "SELECT health_card_json FROM health_cards WHERE return_id = ?",
            (return_id,),
        )
        row = await cursor.fetchone()
        if row:
            return json.loads(row[0])
        return None
```

---

## Environment Variables

| Variable                       | Default             | Description                                                 |
| ------------------------------ | ------------------- | ----------------------------------------------------------- |
| `DATABASE_PATH`                | `second_life.db`    | SQLite database file path                                   |
| `STORAGE_BASE_PATH`            | `storage/`          | Local media storage root                                    |
| `STORAGE_URI_PREFIX`           | `s3://second-life/` | URI prefix for stored files                                 |
| `ANOMALY_MODEL_BASE_PATH`      | `models/`           | Directory for PatchCore model files                         |
| `ANOMALY_BACKEND`              | `heuristic`         | Anomaly detector backend: `heuristic` (OpenCV) or `dinov2` (training-free DINOv2 ViT-S/14 with registers). Falls back to `heuristic` if `torch`/weights are unavailable. |
| `ANOMALY_DEMO_MODE`            | `true`              | If true, simulates anomaly detection with OpenCV heuristics |
| `ANOMALY_INFERENCE_TIMEOUT_MS` | `1500`              | Anomaly detection timeout in milliseconds                   |

---

## Running the Backend

```bash
cd "Module 1/backend"
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Running Tests

```bash
cd "Module 1/backend"
python -m pytest tests/ -v
# 427 tests, ~3 seconds
```

## Running the Frontend

```bash
cd "Module 1/frontend"
npm install
npm run dev
# Runs on http://localhost:5173, proxies /api to http://localhost:8000
```

---

## Key Implementation Details for Integrators

1. **The Health Card is the only output contract.** Don't depend on internal dataclasses (`DispositionResult.gate_applied`, `ScoreBreakdownResult`, etc.) — those are internal pipeline state not exposed via API.

2. **The `flags` field on the P2P-choice-updated Health Card is dynamic** — it's added as raw JSON, not part of the Pydantic model. Parse it as `Optional[list[str]]` from the JSON blob.

3. **Demo mode limitations:**
   - `delivery_date` and `category` are passed in the request body (mock order lookup)
   - `connected_accounts` is always empty (no real social accounts connected)
   - Image URIs are accepted but actual pixel analysis uses placeholder 224×224 black images
   - Fraud scanner produces deterministic results seeded by `customer_id`

4. **To add a new product category**, insert rows into: `return_windows`, `category_weights`, `cost_lookup`, and add a question set to `services/qa_collector.py`.

5. **The pipeline is fully async** — all heavy computation runs in thread pool executors via `asyncio.to_thread()`, so the event loop stays responsive.
