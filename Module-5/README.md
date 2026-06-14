# Module 5 — P2P Exchange: Model & Parameter Documentation

Technical reference for the P2P pricing engine: every model, parameter, and feature.
All paths are relative to `Module-5/`. All inference is **local — no external API**
(hard project constraint + pitch point).

What it does: a seller offers a returned/unused item → we predict the **P2P resale
price** (point + calibrated low/high range + confidence), show the seller their **net
payout** (gross − Amazon facilitation fee), and on **Accept** schedule a (mock) courier
pickup. Condition comes from a **dual path** — Module 1's Health Card when present, else
local **CLIP zero-shot** scoring of the item photos/video.

Pipeline at a glance:
```
ItemListing ─▶ features.extract_features (dual-path) ─▶ pricing.quote ─▶ PriceQuote
                   │  HealthCard? ── yes ─▶ health_score                 (point+range+
                   └─ no ─▶ media.score_condition (CLIP zero-shot)        net payout)
                                       │
                                       ▼
                          model.PriceModel (neural quantile-MLP)
   POST /accept ─▶ pickup.schedule ─▶ PickupJob (scheduled, mock courier)
```

---

## 1. Condition scoring — local CLIP zero-shot (Direct path)

| | |
|---|---|
| **Model** | `clip-ViT-B-32` (OpenAI CLIP) via `sentence-transformers` — `config.clip_model` |
| **Where** | `p2p/media.py` (`score_condition`) |
| **Output** | condition 0–100 from image–text similarity |
| **Fallback** | neutral 50.0 + `is_model_loaded()=False` if torch/CLIP absent |

Embeds photo(s)/video frames and scores condition by similarity against curated prompts
("a brand new unused product" 95 … "a product in poor condition" 30), softmax-weighted;
multi-frame aggregates **80% mean + 20% worst-frame**. Lazy-loaded, graceful fallback.

**Why:** unsupervised, no labels, runs at the edge — same "condition without labels"
thesis as Module 1. **Why not** a fine-tuned defect classifier: no labeled defect set;
CLIP zero-shot is buildable in-hackathon. **Bug fixed (Phase A):** a CPU/CUDA tensor
mismatch silently pinned every Direct score to the 50.0 fallback on GPU machines — the
feature had never actually run on this box. Now device-aligned and verified.

---

## 2. Dual-path features

`features.extract_features(listing) → FeatureVector`. Health Card when present
(`source="health_card"`, condition from `health_score`), else Direct (CLIP). Both produce
the **same 7-feature vector** so one model serves both:

| Feature | Source |
|---|---|
| `condition_score` (0–100) | CLIP / Health Card |
| `original_price` | listing metadata |
| `age_months` | listing metadata |
| `category_demand`, `category_depreciation` | `config.category_tables` lookup |
| `brand_multiplier` | `config.brand_multipliers` |
| `completeness` | has_box + accessories |

---

## 3. Pricing model — neural quantile-MLP (the headline, Phase B)

| | |
|---|---|
| **What** | periodic/PLR numeric embeddings → MLP (256×2, ReLU, dropout 0.1) → 3 pinball heads (q10/q50/q90), sorted → conformal (CQR) interval scaling |
| **Type** | single network — **no boosting, no bagging, no ensemble** (post-2023) |
| **Where** | `p2p/model.py` (`PriceModel`), trained by `p2p/train.py` |
| **Artifact** | `models/quantile_mlp.pt` (weights + scaler + cal_scale); gitignored, regenerable via `python -m p2p.train` |
| **Runtime** | torch + CUDA (CPU fine); lazy-loaded + cached in `pricing` |

Trained in log1p-price space; predictions exponentiated back. Seeded → deterministic.

**Why this:** user required a post-2023, non-ensemble model. The MLP gives **native
calibrated intervals** (point + low/high) from one model, trains on the full synthetic set
(no row cap), and extends to multimodal later.

**What else was considered, and why not:**
- **TabPFN v2** (2025 tabular foundation model) — *rejected*: v8 gates weight download
  behind a Prior-Labs license + `TABPFN_TOKEN` (external credential), caps context ~10k rows.
- **GBM / XGBoost / LightGBM** — *excluded by constraint* (ensembles/boosting). Kept only
  as the eval **baseline**.
- **CARTE / TabICL / TabDPT** — foundation-model flavor but heavier/immature; TabICL is
  classification-only.

### Calibration — the key engineering note
A flexible net **interpolates each point** (sharp median) and the quantile heads **collapse
together** → coverage crashed to ~0.04. Dropout alone was a bimodal knob (collapse ↔
over-wide at 0.99), the wrong tool. Fix: **conformal quantile regression (CQR)** — training
carves a 15% calibration split and picks one scale factor so the central interval hits the
**80% coverage** target. Coverage calibrated to 0.80.

---

## 4. Data — synthetic (honest note)

Trained on a **synthetic** generator (`p2p/synth.py`) built from the feature parameters we
control: nonlinear condition curve, demand×age interaction, and **heteroscedastic**
multiplicative noise (older/poorer items genuinely noisier — which is what gives the
interval something real to learn). Real P2P datasets were **evaluated and rejected**:

| Dataset | Why rejected |
|---|---|
| **MerRec** (real Mercari, `mercari-us/merrec`) | 166 GB total; CC-BY-NC. Loader built + validated (40k items) then removed. |
| **Amazon item-price lite** (~13 MB) | text→price only — no condition signal; would force the deferred text-embedding path. |

Synthetic keeps the model fully **offline, dependency-free**, and lets condition remain a
**learned** feature. Swapping real data in later is a drop-in for `synth.generate_xy`.

---

## 5. Quote assembly & net payout

`pricing.quote(fv) → PriceQuote`. q50→`gross_price`, q10/q90→`low`/`high`,
`confidence = 1 − (high−low)/gross` (clamped). Net payout: `fee = round(gross × fee_rate)`,
`net = gross − fee`; **single rounding source** so structured fields and reason text always
agree (Phase A fix). **Interval guard** (`min_interval_frac=0.03`) keeps `low ≤ gross ≤
high` with a visible band. Every quote is **labeled** with its source
(`model = "neural-quantile-mlp" | "heuristic-fallback"`) — the fallback is never a silent
constant.

---

## 6. Pickup & service

`pickup.schedule(sku_id) → PickupJob` (in-memory event store, mock courier + ETA). FastAPI:
`POST /quote` (ItemListing → PriceQuote), `POST /accept` (→ PickupJob), `GET /pickup/{id}`,
`GET /health` (`model_loaded`/`clip_loaded` reflect **real** lazy-load state — Phase A fix;
pricing model warmed at startup, CLIP opt-in via `P2P_WARM_CLIP=1`).

---

## 7. Results (held-out synthetic split)

Measured vs the retired quantile-GBM baseline on the same split (`python -m p2p.eval`):

| Model | MAE | R² | RMSLE | 80%-coverage |
|---|---|---|---|---|
| baseline quantile-GBM (retired) | 318 | 0.963 | 0.135 | 0.78 |
| **neural quantile-MLP (live)** | **292** | **0.968** | **0.122** | **0.80** |

The MLP **beats the GBM on every metric** and is better-calibrated. The GBM survives only
as the eval baseline in `p2p.eval`; it is **not** in the live path.

---

## 8. Summary of every tunable

| Parameter | Value | File |
|---|---|---|
| `fee_rate` | `0.12` | `config.py` |
| `currency` | `INR` | `config.py` |
| `clip_model` | `clip-ViT-B-32` | `config.py` |
| `min_interval_frac` | `0.03` | `config.py` |
| `mlp_epochs` | `150` | `config.py` |
| `mlp_batch_size` | `512` | `config.py` |
| `mlp_lr` | `2e-3` (cosine schedule) | `config.py` |
| `mlp_dropout` | `0.1` | `config.py` |
| `mlp_weight_decay` | `1e-4` | `config.py` |
| `mlp_hidden` | `256` (×2 layers) | `config.py` |
| `mlp_k` | `16` periodic freqs/feature | `config.py` |
| `synth_n` | `30000` rows | `config.py` |
| quantiles | `(0.1, 0.5, 0.9)` | `model.py` |
| conformal target coverage | `0.80` | `model.py` |
| calibration split | `15%` | `model.py` |
| `category_tables` (base/deprec/demand) | per-category | `config.py` |
| `brand_multipliers` | premium 1.2 / standard 1.0 / value 0.85 | `config.py` |
| condition prompts (CLIP) | 5 prompts, scores 30–95 | `config.py` |

---

## 9. Test coverage

| Group | Tests | Status |
|---|---|---|
| Core (contract, dual-path, pricing monotonicity, payout, pickup, service) | P-suite | ✅ |
| Phase A (media resolution, real-CLIP integration, /health honesty) | +5 | ✅ |
| Phase B (eval metrics, MLP quantile ordering, save/load, fallback labeling) | +6 | ✅ |
| **Total** | **44 + 1 gated** | **All green** |

Heavy CLIP/model work is mocked; the real-CLIP and full-eval (`P2P_RUN_EVAL=1`) tests
self-skip/gate so the suite stays ~15s.

---

## 10. Future work (documented, not built)

- **Real P2P data** behind the same trainer (one MerRec shard, or a licensed feed) — a
  drop-in for `synth.generate_xy`.
- **Multimodal pricing** — CLIP/SigLIP image + text embeddings concatenated into the MLP
  input so price is learned from the photo, not just a condition scalar.
- **Buyer matching** — geo-filtered, reusing Module 2's `retrieve()` (README's original
  Module 5 core).
- **FX-aware multi-currency**; per-segment conformal calibration; real logistics/escrow.
