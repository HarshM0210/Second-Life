# Module 4 — Green Coin: Technical Documentation

Complete reference for the **Sustainability Credits ("Green Coin")** service.
For a quick start, see [`../README.md`](../README.md). For the product
narrative and pitch material, see [`../SecondLIFE_README.md`](../SecondLIFE_README.md).

---

## Table of contents

1. [What this module does](#1-what-this-module-does)
2. [Architecture](#2-architecture)
3. [Directory layout](#3-directory-layout)
4. [Data model — the event-sourced ledger](#4-data-model--the-event-sourced-ledger)
5. [The CO₂e engine](#5-the-co₂e-engine)
6. [Gamification — streaks and badges](#6-gamification--streaks-and-badges)
7. [Rewards catalog](#7-rewards-catalog)
8. [API reference](#8-api-reference)
9. [Configuration](#9-configuration)
10. [Integration with other modules](#10-integration-with-other-modules)
11. [Anti-abuse & guardrails](#11-anti-abuse--guardrails)
12. [Frontend wallet](#12-frontend-wallet)
13. [Running, testing & deployment](#13-running-testing--deployment)
14. [Extending the module](#14-extending-the-module)

---

## 1. What this module does

Green Coin is the **demand-side flywheel** of Second Life commerce. Module 1
grades returned items and routes them into the Renewed supply pool; Green Coin
creates the demand that clears that pool.

Three economic benefits stack, and they are the answer to *"why does Amazon give
coins away?"*:

1. **Reverse-logistics savings** — rewarding a local disposition (donate / P2P /
   keep) avoids a ₹400–600 truck journey; Amazon issues tens of rupees in coins
   to save hundreds.
2. **Renewed demand subsidy** — coins redeem only on Renewed inventory, so every
   redemption clears one more second-hand item at near-zero acquisition cost.
3. **Sustainability reporting** — every coin is backed by an auditable
   **kg CO₂e avoided** number from a tamper-evident ledger.

Mechanically, the service:

- converts a return **disposition** into kg CO₂e avoided, then into coins;
- applies streak multipliers and awards impact badges;
- stores everything as an **append-only ledger** (balance is always `SUM(amount)`);
- lets customers redeem coins on a Renewed-only catalog;
- exposes a platform-wide impact summary for the live demo ticker;
- accepts `purchase_avoidance` events from Module 3 to reward kept items.

---

## 2. Architecture

A single FastAPI service (intended to run on **port 8002**) with a clean layered
design. Dependencies point inward: routes depend on services, services depend on
the domain core and repositories, the core depends on nothing external.

```
                 HTTP (JSON)
                     │
          ┌──────────▼───────────┐
          │  api/  (FastAPI)      │  routes_coins.py, routes_integration.py
          │  - validation         │  thin: validate → call service → shape response
          │  - 503 on failure     │
          └──────────┬───────────┘
                     │
          ┌──────────▼───────────┐
          │  core/ledger_service │  earn / redeem orchestration
          └─────┬──────────┬─────┘
                │          │
   ┌────────────▼──┐   ┌───▼──────────────┐
   │ core/         │   │ db/              │
   │  co2e_engine  │   │  repositories    │  reads/writes over the ledger
   │  gamification │   │  models (ORM)    │
   │  rewards      │   │  database        │  engine / session / get_db
   └───────────────┘   └──────────────────┘
   (pure functions)     (SQLAlchemy / SQLite → Postgres)
```

**Design principles**

- **Event sourcing** — never mutate a balance; append immutable events.
- **Pure domain core** — `co2e_engine` and `gamification` are I/O-free and
  exhaustively unit-tested.
- **Thin routes** — all business logic lives in `LedgerService`, so it is
  reusable (the Module 3 integration route calls the same service).
- **Graceful failure** — endpoints return HTTP 503 on internal error rather than
  crashing, matching Module 3's behaviour.

---

## 3. Directory layout

```
Module-4/
├─ green_coin/
│  ├─ __init__.py
│  ├─ main.py                 FastAPI app factory + lifespan (tables, rewards, CORS)
│  ├─ config.py               pydantic-settings configuration (+ defensive validators)
│  ├─ api/
│  │  ├─ routes_coins.py      public /api/v4/coins/* endpoints
│  │  └─ routes_integration.py  /api/v4/purchase-avoidance (Module 3)
│  ├─ core/
│  │  ├─ co2e_engine.py       Disposition enum + CO₂e/coin math (pure)
│  │  ├─ gamification.py      streak multipliers + badge milestones (pure)
│  │  ├─ rewards.py           rewards catalog loader (cached singleton)
│  │  └─ ledger_service.py    earn/redeem orchestration (EarnResult, RedeemResult)
│  ├─ db/
│  │  ├─ database.py          engine, SessionLocal, Base, get_db dependency
│  │  ├─ models.py            CoinEvent ORM (the ledger table)
│  │  └─ repositories.py      CoinLedgerRepository (all ledger reads/writes)
│  ├─ schemas/
│  │  └─ coins.py             Pydantic request/response models
│  └─ requirements.txt
├─ data/rewards.json          redeemable catalog (Renewed-only by design)
├─ frontend/wallet.html       self-contained React wallet UI (no build step)
├─ tests/                     conftest + 28 unit & API tests
├─ pytest.ini
├─ README.md                  quick start
├─ DOCUMENTATION.md           (this file lives in docs/)
└─ SecondLIFE_README.md       full product spec
```

---

## 4. Data model — the event-sourced ledger

A single table, `coin_events`, defined by `db/models.py::CoinEvent`. **The ledger
is append-only.** A user's balance is `SUM(amount)`; their lifetime CO₂e is the
sum of `co2e_kg` over `earned` events. Nothing is ever updated in place.

### `coin_events`

| Column | Type | Notes |
|---|---|---|
| `id` | TEXT (PK) | uuid4 |
| `user_id` | TEXT | indexed |
| `event_type` | TEXT | `earned` \| `redeemed` \| `expired` \| `badge_earned` (CHECK constrained) |
| `amount` | INTEGER | `+` earned, `−` redeemed/expired, `0` for badge_earned |
| `source` | TEXT | e.g. `disposition:DONATE_LOCAL`, `bonus:chose_renewed`, `reward:prime_1month`, `badge:seed_saver` |
| `co2e_kg` | REAL | kg CO₂e avoided (0.0 for non-earn events) |
| `streak_day` | INTEGER | streak at time of the event |
| `badge` | TEXT (nullable) | badge slug if this event unlocked one |
| `item_id` | TEXT (nullable) | order/item reference |
| `created_at` | DATETIME | UTC, server-defaulted |

**Indexes:** `(user_id)`, `(user_id, event_type)`, `(created_at)`.

### Why event sourcing

- **Auditability** — every coin's provenance is a row; the impact certificate can
  be cryptographically reconstructed.
- **Fraud is a query** — "users who earned >2,000 coins in 24h" is one `SUM` with
  a time filter.
- **Expiry is trivial** — emit a negative `expired` event; never touch history.

### Repository methods (`db/repositories.py::CoinLedgerRepository`)

| Method | Returns | Purpose |
|---|---|---|
| `add_event(...)` | `CoinEvent` | insert + flush a single immutable event |
| `get_balance(db, user_id)` | `int` | `SUM(amount)` for the user |
| `get_co2e_total(db, user_id)` | `float` | `SUM(co2e_kg)` over earned events |
| `get_history(db, user_id, limit=20)` | `list[CoinEvent]` | newest-first activity |
| `get_last_earn_event(db, user_id)` | `CoinEvent \| None` | drives streak calc |
| `coins_earned_last_24h(db, user_id)` | `int` | anti-abuse fraud flag |
| `platform_co2e_total(db)` | `float` | impact ticker |
| `platform_items_count(db)` | `int` | distinct items given a second life |

---

## 5. The CO₂e engine

`core/co2e_engine.py` — pure functions, no I/O. This is the scientific backbone:
coins are issued *from CO₂e*, never invented.

### Dispositions

```
P2P_LOCAL | DONATE_LOCAL | KEEP | REFURBISH | RESELL | RECYCLE | RETURN_FC
```

`RETURN_FC` is the **baseline** (ship back to a fulfillment center) and earns
zero — everything else is measured as avoidance relative to it.

### Constants

| Constant | Value | Source |
|---|---|---|
| `EF_ROAD_KG_PER_KG_KM` | `0.089 / 1000` | GLEC Framework / ISO 14083 |
| `BASELINE_DISTANCE_KM` | `300` | assumed average one-way to FC |
| `BASELINE_ITEM_WEIGHT_KG` | `0.5` | configurable per category |
| `MANUFACTURE_AVOIDED` | electronics 45, appliances 30, clothing 12, footwear 8, toys 5, books 1.5, default 10 (kg) | LCA literature / ecoinvent |
| `COIN_MULTIPLIER` | `10` | 1 kg CO₂e avoided = 10 coins (overridable via config) |

### Functions

```python
baseline_co2e(item_weight_kg=0.5) -> float
co2e_avoided(disposition, category, item_weight_kg=0.5, buyer_distance_km=0.0) -> float
coins_earned(co2e_kg, multiplier=10) -> int          # never negative
equivalents(co2e_kg) -> {"trees_per_month", "km_not_driven", "phone_charges"}
```

`co2e_avoided` accepts either a `Disposition` enum or its string form. The
avoidance formula per disposition:

| Disposition | Formula (`base` = baseline, `mfg` = manufacture-avoided) |
|---|---|
| `P2P_LOCAL` | `base + mfg − (weight × max(buyer_km, 5) × EF_ROAD)` |
| `DONATE_LOCAL` | `base + 0.70 × mfg` |
| `KEEP` | `base + mfg` |
| `REFURBISH` | `base + 0.85 × mfg` |
| `RESELL` | `base + 0.75 × mfg` |
| `RECYCLE` | `0.60 × base` |
| `RETURN_FC` / unknown | `0.0` |

> **Note on the numbers:** with `BASELINE_DISTANCE_KM = 300` the transport
> baseline (~0.013 kg) is small relative to manufacture-avoidance, so manufacture
> avoidance dominates the score. The `SecondLIFE_README.md` illustrative table
> uses larger headline figures; the **code formula above is the source of
> truth**. To make P2P the dramatic top reward (as in the pitch table), raise
> `BASELINE_DISTANCE_KM` or weight the P2P manufacture credit. See
> [§14](#14-extending-the-module).

---

## 6. Gamification — streaks and badges

`core/gamification.py` — pure functions and data.

### Streak multiplier

```python
apply_streak_multiplier(base_coins, current_streak) -> int
#   streak >= 7  -> 1.5×
#   streak >= 3  -> 1.2×
#   otherwise    -> 1.0×
```

### Streak progression

```python
compute_new_streak(last_earn_at, last_streak, now, reset_hours=48) -> int
```

- First-ever earn → `1`.
- Gap larger than `reset_hours` → reset to `1`.
- Same calendar day as last earn → unchanged.
- Next day within the window → increment.

### Badges

Awarded at cumulative-CO₂e thresholds (ascending):

| Slug | Badge | Icon | Threshold | Equivalent |
|---|---|---|---|---|
| `seed_saver` | Seed Saver | 🌱 | 5 kg | 6 trees planted |
| `green_guardian` | Green Guardian | 🌿 | 25 kg | Skipped 119 km of driving |
| `forest_keeper` | Forest Keeper | 🌳 | 100 kg | Powered a home for 2 weeks |
| `planet_protector` | Planet Protector | 🌍 | 500 kg | Offset a flight Mumbai→Delhi |

```python
newly_earned_badge(previous_total_kg, new_total_kg) -> Badge | None  # highest crossed
unlocked_badges(total_kg) -> list[Badge]
```

When an earn event crosses a threshold, the service writes a separate
`badge_earned` ledger row (audit trail) and returns the badge in the response.

---

## 7. Rewards catalog

`core/rewards.py` loads `data/rewards.json` into a cached singleton at startup
(raises `RuntimeError` if the file is missing or malformed — the service refuses
to start without a valid catalog). Redemption is **restricted to
sustainability-positive rewards by design** — that restriction *is* the demand
subsidy that closes the loop.

| `reward_id` | Name | Cost | Category |
|---|---|---|---|
| `renewed_discount_100` | ₹10 off any Renewed product | 100 | renewed_discount |
| `renewed_flash_access_250` | Priority Renewed flash-sale access | 250 | renewed_discount |
| `prime_1month_1000` | 1 month Prime membership | 1000 | membership |
| `impact_certificate_500` | Green Impact Certificate (PDF) | 500 | certificate |
| `donate_ngo_reforestation` | Donate coins to NGO reforestation | 100 | donation |

---

## 8. API reference

Base URL (local): `http://localhost:8002`. Interactive docs at `/docs`.

All data endpoints return **HTTP 503** with `{"detail": "Service temporarily
unavailable"}` on an internal/DB error (`/health` is a plain liveness probe with
no dependencies). Validation errors return **422** (FastAPI default). Note that
`/redeem` and `/purchase-avoidance` failures (insufficient balance, unknown
reward) are **not** HTTP errors — they return **200** with a `success`/`accepted`
flag, so callers must inspect the body, not just the status code.

### `GET /health`

Liveness probe.

```json
{ "status": "ok", "service": "green_coin", "version": "0.1.0" }
```

---

### `POST /api/v4/coins/earn`

Issue coins for a return disposition. **Called by Module 1** after routing.

**Request**

| Field | Type | Required | Default |
|---|---|---|---|
| `user_id` | string | yes | — |
| `disposition` | enum | yes | — |
| `category` | string | yes | — |
| `item_id` | string | yes | — |
| `item_weight_kg` | float > 0 | no | 0.5 |
| `buyer_distance_km` | float ≥ 0 | no | 0.0 |

```jsonc
// → 200
{
  "coins_earned": 56,
  "co2e_kg": 5.61,
  "new_balance": 56,
  "streak": 1,
  "badge_unlocked": {
    "slug": "seed_saver", "name": "Seed Saver", "icon": "🌱",
    "threshold_kg": 5.0, "equivalent": "6 trees planted", "unlocked": true
  },
  "equivalents": { "trees_per_month": 6.8, "km_not_driven": 26.7, "phone_charges": 701 },
  "flagged_for_review": false
}
```

Pipeline: `co2e_avoided` → `coins_earned` → streak multiplier → cap at
`EARN_CAP_PER_EVENT` → badge check → persist `earned` (and `badge_earned`) rows →
24h fraud flag → commit.

---

### `POST /api/v4/coins/earn/bonus`

Fixed-coin behavioural reward. Used by **Module 2** (chose Renewed, +50),
**Module 5** (P2P referral, +25), onboarding (+100), etc. One endpoint covers
all bonus triggers via the `source` string.

**Request**

| Field | Type | Required |
|---|---|---|
| `user_id` | string | yes |
| `coins` | int > 0 | yes |
| `source` | string | yes |
| `item_id` | string | no |

```jsonc
// → 200
{ "coins_earned": 50, "new_balance": 50, "source": "chose_renewed" }
```

Bonus coins are also capped at `EARN_CAP_PER_EVENT`.

---

### `POST /api/v4/coins/redeem`

Spend coins on a catalog reward.

**Request:** `{ "user_id": "...", "reward_id": "renewed_discount_100" }`

```jsonc
// → 200 (success)
{ "success": true, "new_balance": 0, "reward_id": "renewed_discount_100", "reason": null }

// → 200 (failure — never an HTTP error)
{ "success": false, "new_balance": 40, "reward_id": "prime_1month_1000", "reason": "insufficient_balance" }
// reason ∈ { "insufficient_balance", "unknown_reward" }
```

---

### `GET /api/v4/coins/wallet/{user_id}`

Full wallet view for the UI.

```jsonc
// → 200
{
  "user_id": "priya",
  "balance": 96,
  "co2e_total_kg": 5.61,
  "equivalents": { "trees_per_month": 6.8, "km_not_driven": 26.7, "phone_charges": 701 },
  "badges": [ { "slug": "seed_saver", "...": "...", "unlocked": true }, "... all 4 badges with unlocked flags ..." ],
  "history": [
    { "id": "uuid", "event_type": "earned", "amount": 56, "source": "disposition:DONATE_LOCAL",
      "co2e_kg": 5.61, "streak_day": 1, "badge": "seed_saver", "item_id": "shoe-1",
      "created_at": "2026-06-14T10:00:00+00:00" }
  ]
}
```

`badges` always returns all four, each with an `unlocked` boolean derived from
the user's cumulative CO₂e. `history` is the 20 most recent events.

---

### `GET /api/v4/coins/impact/summary`

Platform-wide totals — powers the live demo ticker.

```jsonc
// → 200
{ "co2e_avoided_kg": 2847.0, "items_given_second_life": 891, "trees_equivalent": 3430.1 }
```

---

### `GET /api/v4/coins/rewards`

Returns the redeemable catalog (array of `{reward_id, name, cost, description, category}`).

---

### `POST /api/v4/purchase-avoidance`

**Consumed by Module 3.** Mirrors Module 3's `PurchaseAvoidanceEvent` schema
exactly. Rewards a customer who kept an item after a nudge with
`KEPT_AFTER_NUDGE_COINS` (default 40).

**Request**

```jsonc
{
  "event_type": "purchase_avoidance",
  "customer_id": "cust-9",
  "product_id": "prod-9",
  "risk_score": 0.82,
  "intervention_type": "SIZE_GUIDANCE",
  "session_id": "sess-1",
  "emitted_at": "2026-06-14T10:00:00Z"
}
```

```jsonc
// → 200
{ "accepted": true, "coins_earned": 40, "new_balance": 40 }
```

---

## 9. Configuration

`config.py` uses `pydantic-settings`; every field is overridable via environment
variable or a `.env` file. Numeric fields have defensive validators — an invalid
value is **logged and replaced with the default** rather than crashing startup.

| Setting | Env var | Default | Purpose |
|---|---|---|---|
| `DB_URL` | `DB_URL` | `sqlite:///./green_coin.db` | database connection |
| `REWARDS_PATH` | `REWARDS_PATH` | `data/rewards.json` | catalog file |
| `COIN_MULTIPLIER` | `COIN_MULTIPLIER` | `10` | coins per kg CO₂e |
| `EARN_CAP_PER_EVENT` | `EARN_CAP_PER_EVENT` | `500` | max coins per earn |
| `FRAUD_DAILY_THRESHOLD` | `FRAUD_DAILY_THRESHOLD` | `2000` | 24h fraud flag |
| `KEPT_AFTER_NUDGE_COINS` | `KEPT_AFTER_NUDGE_COINS` | `40` | Module 3 reward |
| `STREAK_RESET_HOURS` | `STREAK_RESET_HOURS` | `48` | streak reset window |

Example `.env`:

```env
DB_URL=postgresql+psycopg://user:pass@db:5432/greencoin
COIN_MULTIPLIER=10
EARN_CAP_PER_EVENT=500
```

---

## 10. Integration with other modules

The Health Card JSON and these HTTP calls are the inter-module contract.

| Module | Direction | Endpoint | Payload |
|---|---|---|---|
| **Module 1** (Grading/Routing) | → Green Coin | `POST /api/v4/coins/earn` | disposition + category + item |
| **Module 3** (Return Prevention) | → Green Coin | `POST /api/v4/purchase-avoidance` | `PurchaseAvoidanceEvent` (already wired) |
| **Module 2** (Recommend) | → Green Coin | `POST /api/v4/coins/earn/bonus` | `source: "chose_renewed"` (+50) |
| **Module 5** (P2P) | → Green Coin | `POST /api/v4/coins/earn/bonus` | `source: "p2p_referral"` (+25) |

**Module 3 is already configured** — its `integrations/green_coin.py` emitter
posts to `GREEN_COIN_BASE_URL` (default `http://localhost:8002`) at
`/api/v4/purchase-avoidance` with retry-and-log-on-failure. No change needed on
its side; our endpoint accepts that exact schema.

> **Port alignment:** this service must run on **8002** to match Module 3's
> configured base URL. If Modules 1/2/5 hardcode a different URL, reconcile at
> integration time.
>
> **Module 1 field mapping:** the `/earn` body follows the README's `EarnRequest`
> shape. If Module 1 forwards its full Health Card JSON instead, add a thin
> adapter (extract `disposition` + `category`) — see [§14](#14-extending-the-module).

---

## 11. Anti-abuse & guardrails

- **Per-event earn cap** — both `/earn` and `/earn/bonus` clamp to
  `EARN_CAP_PER_EVENT` (500), preventing gaming via inflated fake returns.
- **24h fraud flag** — if a user's trailing-24h earnings exceed
  `FRAUD_DAILY_THRESHOLD` (2000), the earn is still honoured but
  `flagged_for_review: true` is returned and a warning is logged.
- **Non-cashable** — coins are account-bound, redeemable only (no ₹ withdrawal),
  which keeps them out of financial-instrument regulation.
- **Restricted redemption** — Renewed-only catalog ensures coins drive circular
  transactions, not new-manufacture subsidies.
- **Append-only ledger** — coin expiry and reversals are negative events, never
  history rewrites; the SHA-256 impact certificate is reconstructable from rows.

---

## 12. Frontend wallet

`frontend/wallet.html` is a **self-contained** React app (React + Babel via CDN,
no build step) — chosen so the demo can't break on a toolchain failure. Open it
in a browser with the service running on `:8002`.

Components:

- **Ticker** — polls `/impact/summary` every 10s (the live "ticking" beat).
- **Hero** — animated count-up balance + lifetime CO₂e and equivalents.
- **Simulator** — "process a returned item" panel to drive Priya's demo moment
  (pick disposition/category/distance → `POST /earn` → watch the badge unlock).
- **Timeline** — recent ledger activity with `+`/`−` indicators.
- **BadgeShelf** — four badges, greyscale until unlocked.
- **RedeemCatalog** — reward tiles, button disabled when balance < cost.

The hardcoded demo user is `priya` (`const USER = "priya"`).

---

## 13. Running, testing & deployment

### Local run

```bash
cd Module-4
pip install -r green_coin/requirements.txt
uvicorn green_coin.main:app --reload --port 8002
```

Startup (lifespan): create tables → load rewards catalog → enable CORS. Then
open `frontend/wallet.html`.

### Tests

```bash
cd Module-4
python -m pytest -q     # 28 passed
```

- `tests/test_co2e_engine.py` — CO₂e + coin math.
- `tests/test_gamification.py` — streaks + badges.
- `tests/test_api.py` — full earn → wallet → redeem flow + Module 3 integration.
- `tests/conftest.py` — per-test in-memory SQLite (`StaticPool`) with `get_db`
  overridden; rewards loaded from `data/rewards.json`.

### Production path

- **Database:** swap `DB_URL` to Postgres (`postgresql+psycopg://...`). The ORM
  and repositories are unchanged; only the connection string differs.
- **Media:** anomaly heatmaps / certificates → S3 (object store).
- **CORS:** `main.py` currently allows all origins for the demo — restrict
  `allow_origins` to the real frontend domain in production.
- **Deploy:** CPU-only; no GPU dependency. Containerize and run behind the same
  gateway as the other module services.

---

## 14. Extending the module

**Add a reward** — append an entry to `data/rewards.json` (it is validated
against the `Reward` schema at startup). No code change.

**Add a bonus trigger** — just call `/api/v4/coins/earn/bonus` with a new
`source` string. No new logic needed.

**Tune the economics** — change `COIN_MULTIPLIER`, `EARN_CAP_PER_EVENT`, badge
thresholds (`gamification.BADGES`), or emission factors (`co2e_engine`).

**Make P2P the headline reward** (match the pitch table) — increase
`BASELINE_DISTANCE_KM` (a longer avoided journey raises every non-baseline
disposition, and P2P most of all relative to the others), or add a dedicated P2P
manufacture bonus in `co2e_avoided`.

**Adapt to Module 1's Health Card** — if Module 1 sends the full Health Card
JSON rather than the `EarnRequest` shape, add an adapter at the top of `/earn`
that extracts `disposition` and `category` from the card before calling
`LedgerService.earn_for_disposition`.

**Coin expiry job** — a nightly script: find users with no event in 12 months,
insert a negative `expired` event for their balance. The append-only design
makes this ~10 lines.

**Impact certificate** — generate `sha256(user_id + co2e_total + timestamp)` and
render a PDF (e.g. `reportlab`); store the hash as a `badge_earned`-style audit
row for tamper-evident verification.
```
