# Module 4 — Sustainability Credits ("Green Coin")

The **demand-side flywheel** of Second Life commerce. Module 1 grades and routes
returned items into the Renewed supply pool; Green Coin creates the *demand* that
clears it. Every coin is backed by a defensible **kg CO₂e avoided** number and is
redeemable only on sustainability-positive actions (overwhelmingly Renewed
inventory), so every redemption drives one more circular transaction.

> *"Grading creates supply. Green Coin creates demand. The long tail finally gets a second life."*

## What's here

```
Module-4/
├─ green_coin/                 FastAPI service (runs on port 8002)
│  ├─ main.py                  app factory + lifespan (create tables, load rewards)
│  ├─ config.py                pydantic-settings config (mirrors Module 3)
│  ├─ core/
│  │  ├─ co2e_engine.py        pure CO₂e + coin math (Disposition enum, factors)
│  │  ├─ gamification.py       streak multipliers + impact badges
│  │  ├─ rewards.py            rewards catalog loader
│  │  └─ ledger_service.py     earn/redeem orchestration
│  ├─ db/                      SQLAlchemy event-sourced ledger (CoinEvent)
│  ├─ schemas/coins.py         Pydantic request/response models
│  └─ api/
│     ├─ routes_coins.py       /earn /redeem /wallet /impact/summary /rewards
│     └─ routes_integration.py /purchase-avoidance (Module 3 contract)
├─ data/rewards.json           redeemable catalog (Renewed-only by design)
├─ frontend/wallet.html        self-contained React wallet UI (no build step)
└─ tests/                      28 unit + API tests
```

## Run it

```bash
cd Module-4
pip install -r green_coin/requirements.txt
uvicorn green_coin.main:app --reload --port 8002
```

Then open `frontend/wallet.html` in a browser. The wallet talks to the service on
`localhost:8002`. Use the **"Demo: process a returned item"** panel to drive
Priya's moment live (issue coins, watch the badge unlock + count-up animation).

Interactive API docs: <http://localhost:8002/docs>

## Tests

```bash
cd Module-4
python -m pytest -q        # 28 passed
```

## API (prefix `/api/v4`)

| Method | Path | Purpose | Caller |
|---|---|---|---|
| POST | `/coins/earn` | Issue coins for a return disposition | **Module 1** |
| POST | `/coins/earn/bonus` | Fixed-coin behavioural reward | Module 2 / 5 / onboarding |
| POST | `/coins/redeem` | Spend coins on a Renewed reward | Wallet UI |
| GET | `/coins/wallet/{user_id}` | Balance, CO₂e, badges, history | Wallet UI |
| GET | `/coins/impact/summary` | Platform-wide ticker totals | Ticker |
| GET | `/coins/rewards` | Redeemable catalog | Wallet UI |
| POST | `/purchase-avoidance` | Reward a kept item (+40 coins) | **Module 3** |

### Earn example (what Module 1 sends after routing)

```jsonc
// POST /api/v4/coins/earn
{ "user_id": "priya", "disposition": "DONATE_LOCAL",
  "category": "footwear", "item_id": "shoe-123" }
// → { "coins_earned": 56, "co2e_kg": 5.61, "new_balance": 56,
//     "streak": 1, "badge_unlocked": {"slug":"seed_saver", ...},
//     "equivalents": {...}, "flagged_for_review": false }
```

`disposition` is one of `P2P_LOCAL | DONATE_LOCAL | KEEP | REFURBISH | RESELL |
RECYCLE | RETURN_FC` (`RETURN_FC` is the baseline and earns 0).

## How it integrates with the other modules

- **Module 1 (Grading/Routing):** after it picks a disposition, it makes one
  `POST /api/v4/coins/earn` call. That's the whole wiring.
- **Module 3 (Return Prevention):** already configured to POST its
  `PurchaseAvoidanceEvent` to `http://localhost:8002/api/v4/purchase-avoidance`
  (`GREEN_COIN_BASE_URL` in its config). We accept that exact schema and reward
  the kept item with `KEPT_AFTER_NUDGE_COINS` (default 40). No changes needed on
  Module 3's side.
- **Module 2 (Recommend) / Module 5 (P2P):** fire `POST /coins/earn/bonus`
  (e.g. `source: "chose_renewed"`, `source: "p2p_referral"`) — one call each.

## Design notes (for the pitch / judges)

- **Event-sourced ledger** — `coin_events` is append-only; balance is always
  `SUM(amount)`. Full audit trail, fraud is a query, expiry is a 10-line script.
- **CO₂e is the backbone** — coins are issued from `co2e_avoided()`, grounded in
  GLEC/ISO 14083 transport factors and LCA manufacture-avoidance figures.
- **Restricted redemption is intentional** — coins clear Renewed inventory, never
  subsidise new manufacture. That's the closed loop.
- **Anti-abuse built in** — per-event earn cap (`EARN_CAP_PER_EVENT`, 500) and a
  24h fraud flag (`FRAUD_DAILY_THRESHOLD`, 2000).
- **Graceful degradation** — all endpoints return 503 (not crash) on internal
  failure, matching Module 3's behaviour.

See `SecondLIFE_README.md` for the full product narrative and roadmap (DPP, India
GCP integration, real LCA data, dynamic CO₂e routing).
```
