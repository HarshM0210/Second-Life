# Module 2 — Recommendation Model

Technical reference for every model, parameter, and threshold in the Recommendation
module. For each: **what** it is, the **value** we use, **why** we chose it, and **what
else** could have been done. All paths are relative to `Module-2/`. All inference is
**local — no external API** (a hard project constraint and a pitch point).

Pipeline at a glance:

```
UserContext ──▶ profile.assemble_profile_text ──▶ embedder.embed_text ──┐
   (+ consent-gated social signals, §12)                                ▼
catalog text ─▶ embedder.embed_catalog (precomputed once) ─▶ retrieve.retrieve (cosine)
                                                                        ▼
                          [optional cross-encoder] ─▶ rerank.rerank (Renewed/health boost) ──▶ Feed
```

---

## 1. Text embedding model

|                                                 |                                                                                                                  |
| ----------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| **Model**                                       | `Alibaba-NLP/gte-modernbert-base` (`config.EmbedConfig.text_model`) — Phase 2.1 upgrade from `bge-small-en-v1.5` |
| **Dimension**                                   | `768` (`EmbedConfig.dim`)                                                                                        |
| **Normalization**                               | L2 / unit vectors — `normalize_embeddings=True`                                                                  |
| **Batch size**                                  | `64` (`embed_texts`, catalog precompute)                                                                         |
| **Runtime**                                     | sentence-transformers (`trust_remote_code`), CPU-fine, lazy-loaded once, cached to `~/.cache/huggingface`        |
| **Where**                                       | `recommend/embedder.py`                                                                                          |
| **Eval (real ESCI, 50 pooled negatives/query)** | **NDCG@10 = 0.4660** vs bge-small 0.4634 — a _marginal_ win (§11).                                               |
| **Status**                                      | **Current/implemented.**                                                                                         |

> **Phase 2.1 honesty note.** The embedder was upgraded `bge-small` (384-dim, 2023) →
> `gte-modernbert-base` (768-dim, ModernBERT arch, early 2025). On the _valid_ ESCI eval
> (proper candidate pools) it wins by only **+0.0026 NDCG@10** while being ~2× the size
> and latency — so **`bge-small` remains a legitimate lighter fallback**. The
> originally-assigned **EmbeddingGemma** (Sep 2025) was not used — license-gated on HF;
> `gte-modernbert` was the ungated 2025-era stand-in. The solidly-2025 component is the
> Qwen3-Reranker (§11).

**Why this model.** Small + CPU-friendly (sub-second at demo scale, no GPU dependency);
strong-for-size on short product text; local + free (no API); L2-normalized so cosine =
dot product on a clean `[-1,1]` scale the rerank weights are tuned against.

**Why these values.** `dim=768` fixed by the model (recorded so the hash-fallback matches
shape); `batch_size=64` a CPU throughput/memory midpoint (one-time startup cost);
`normalize_embeddings=True` essential — the §5 weights assume the normalized cosine scale.

**What else.** Larger embedder (`bge-base/large`) for recall at higher cost; instruction
query prefix (free few-point lift); domain fine-tuning on Amazon query→click; multilingual
`bge-m3` for the India story (vision roadmap).

---

## 2. Image embedding model (declared, not wired)

|            |                                               |
| ---------- | --------------------------------------------- |
| **Model**  | `ViT-B/32` (CLIP) — `EmbedConfig.image_model` |
| **Status** | **Configured but unused** by the pipeline     |

The README lists CLIP for image matching, so the config slot is reserved. Not wired
because it adds ~600 MB–1 GB of torch/CLIP weight for marginal demo gain, and text
similarity alone clears the resale-feed use case. **What else:** embed product photos +
fuse image/text similarity; feed Module 1's anomaly heatmap into ranking.

---

## 3. Offline hash-embed fallback

|             |                                                                                              |
| ----------- | -------------------------------------------------------------------------------------------- |
| **What**    | Deterministic bag-of-words hashed into `dim` buckets (MD5 → bucket), L2-normalized           |
| **Where**   | `embedder._hash_embed`                                                                       |
| **Trigger** | model load/encode failure, or `use_model=False`                                              |
| **Guard**   | `validate_embedder()` + density check (`>50%` non-zero) refuses this path at service startup |

Lets the whole pipeline + tests run offline with **zero model download** (~5 MB). Not
semantically meaningful — a shape/determinism stand-in. Per Ross R8 the service **fails
loud** rather than silently serving these (`/health` reports `model_loaded`). **What else:**
a TF-IDF/hashing-vectorizer fallback would give real lexical signal offline.

---

## 4. Retrieval

|               |                                                                  |
| ------------- | ---------------------------------------------------------------- |
| **Method**    | Exhaustive cosine similarity, full scan                          |
| **Tie-break** | similarity desc, then `sku_id` asc (deterministic)               |
| **Where**     | `recommend/retrieve.py` (`cosine_similarity`, `retrieve`)        |
| **Purity**    | No business rules — reusable by Module 5 (P2P) with a geo filter |

At demo scale (8 SKUs; tested to 5k) brute-force cosine is **~103 ms at 5k** (Ross R2),
well under budget. `retrieve()` is kept a **pure** function of (vector, vectors) so Module
5 can wrap it with distance filtering. Deterministic tie-break → reproducible, snapshot-
testable feeds. **What else:** ANN (FAISS/hnswlib) for 10⁵–10⁷ SKUs; hybrid dense+BM25;
category/price pre-filtering.

---

## 5. Re-ranking (the headline behavior)

All weights live in `config.RerankConfig` — one block, intentionally not scattered.

| Parameter               | Value   | Meaning                                                  |
| ----------------------- | ------- | -------------------------------------------------------- |
| `renewed_boost_weight`  | `0.18`  | Max additive boost for a perfect-health Renewed item     |
| `health_score_floor`    | `70.0`  | Below this health score, **no** boost                    |
| `health_score_ceil`     | `100.0` | Boost saturates here                                     |
| `discount_boost_weight` | `0.04`  | Extra nudge scaled by genuine discount vs original price |
| `min_confidence`        | `0.30`  | Health Cards below this confidence get no boost          |

**Scoring formula** (`rerank._renewed_boost`):

```
final_score = cosine_similarity
            + renewed_boost_weight · clamp((health_score − floor)/(ceil − floor), 0, 1)
            + discount_boost_weight · discount_frac          # only if discount > 0
```

Boost applies **only** when `is_renewed`, `confidence ≥ min_confidence`, and
`health_score ≥ floor`. New items / missing Health Cards score on similarity alone.

**Why these values.** `0.18` is sized against the cosine scale — on the Priya demo the

> 90 Renewed Nike clears the equivalent New Nike by ~14% (a _visible_ gap, asserted in
> tests), big enough to show the resale-clears thesis, small enough that an irrelevant
> Renewed item can't outrank a strong semantic match. `floor=70` mirrors Module 1's
> "refurbish then list" threshold (only up-rank inventory good enough to sell as Renewed).
> `ceil=100` gives a proportional ramp. `discount=0.04` is ~4× smaller than health — a price
> cut _nudges_, doesn't dominate. `min_confidence=0.30` — don't boost what the grader itself
> is unsure about.

**Why additive (not multiplicative).** Keeps each factor **traceable** for a stacked
score-breakdown — serves the Trust Layer explainability pillar.

**What else.** Learned weights — the biggest upgrade and `Plan.md §0`'s thesis: a
**market-aware contextual bandit** (inventory glut / nearby demand / logistics cost) that
_learns_ the boost. Static weights are the 🟢 demo rung; LinUCB (🟡) and offline RL + OPE
(🔴) are the stretch rungs. Also: market-state slider that flips ranking live (Plan.md
killer demo moment); MMR diversity; cross-encoder rerank (§11); a margin/CO₂e objective term.

---

## 6. Profile assembly

| Parameter               | Value                             | Where                           |
| ----------------------- | --------------------------------- | ------------------------------- |
| Wishlist weight         | **2×** (repeated)                 | `profile.assemble_profile_text` |
| Search-history weight   | **2×**                            | same                            |
| Purchase-history weight | **1×**                            | same                            |
| Trends weight           | **1×**                            | same                            |
| Social interests        | consent-gated, weighted (§12)     | `social.extract_social_text`    |
| Renewed enrichment      | condition + `"{x}% off"` appended | `profile._enrich_sku`           |

The user becomes one text blob we embed. Wishlist/searches signal _current intent_ (2×);
past purchases are weaker/staler (1×). SKU ids are resolved to real titles + Renewed
condition/discount context so the embedding captures _meaning_, not opaque ids. **What
else:** continuous recency decay; separate query vectors combined at similarity stage;
negative signals from returns (Module 3); exclude owned items (§8).

---

## 7. Reason-string generation

| Reason                                          | Trigger                                               | Where                     |
| ----------------------------------------------- | ----------------------------------------------------- | ------------------------- |
| `"matches wishlist"`                            | SKU in wishlist                                       | `pipeline._build_reasons` |
| `"previously purchased"`                        | SKU in history                                        | same                      |
| `"similar to past purchase"`                    | cosine to any history item **> 0.7**                  | same                      |
| `"trending in {trend}"`                         | trend term appears in SKU text                        | same                      |
| `"matches your social interests"`               | social token appears in SKU text (consent-gated, §12) | same                      |
| `"Renewed, health {n}"` / `"{n}% off original"` | from the Renewed boost                                | `rerank._renewed_boost`   |

Powers the demo's "why this item" / Trust-Layer story. The `0.7` cosine bar reliably means
same-category on the normalized scale, so it doesn't fire spuriously. **What else:** make
`0.7` a named config constant and tune it; richer NL reasons (local LLM, added risk).

---

## 8. Data

**Status: 100% synthetic, by design.** 8 hand-authored SKUs, 8 Health Cards, 4 personas in
`fixtures/`. The embeddings over them are _real_ gte-modernbert vectors; only the inputs are
synthetic. README/Plan.md §8 advise "use synthetic data but _say_ it's synthetic." Fixtures
keep the module dependency-free; the service reads `RECOMMEND_CATALOG` /
`RECOMMEND_HEALTH_CARDS` env vars with fixtures as fallback, so real data is a config swap
(gated on G3; tracked as R4). **Known behavior (R9):** already-purchased items appear in the
feed (pinned in tests, not silently filtered) — a product decision. **What else:** seed a
few hundred real titles from a public dump; real Health Cards (R4); synthetic user logs to
train the §5 bandit.

---

## 9. Summary of every tunable

| Parameter                         | Value                             | File                   |
| --------------------------------- | --------------------------------- | ---------------------- |
| `text_model`                      | `Alibaba-NLP/gte-modernbert-base` | `config.py`            |
| `image_model` (unused)            | `ViT-B/32`                        | `config.py`            |
| `dim`                             | `768`                             | `config.py`            |
| `batch_size`                      | `64`                              | `embedder.py`          |
| `normalize_embeddings`            | `True`                            | `embedder.py`          |
| density-guard threshold           | `>0.5 · dim`                      | `embedder.py`          |
| `renewed_boost_weight`            | `0.18`                            | `config.py`            |
| `health_score_floor`              | `70.0`                            | `config.py`            |
| `health_score_ceil`               | `100.0`                           | `config.py`            |
| `discount_boost_weight`           | `0.04`                            | `config.py`            |
| `min_confidence`                  | `0.30`                            | `config.py`            |
| wishlist / search weight          | `2×`                              | `profile.py`           |
| history / trends weight           | `1×`                              | `profile.py`           |
| social follows/likes weight       | `2×`                              | `config.py` (`SOCIAL`) |
| social topics/captions weight     | `1×`                              | `config.py` (`SOCIAL`) |
| "similar to past purchase" cosine | `0.7` (inline)                    | `pipeline.py`          |
| retrieval                         | exhaustive cosine                 | `retrieve.py`          |

**The one upgrade that matters most:** replace the hand-tuned §5 weights with a
market-aware learned policy (Plan.md §0) — the jump from "competent recommender" to the
project's differentiating thesis.

---

## 10. Cross-encoder reranker (opt-in)

|             |                                                                              |
| ----------- | ---------------------------------------------------------------------------- |
| **Model**   | `Qwen/Qwen3-Reranker-0.6B` (Jun 2025, Alibaba), `recommend/cross_encoder.py` |
| **Stage**   | re-scores top-20 candidates after `retrieve()` (purity preserved)            |
| **Default** | **OFF** (`use_cross_encoder=False`)                                          |

Verified working on direct pairs (2.19 vs −10.4 logits) but **flat on ESCI** (0.4656 vs
0.4660 retrieval-only) — on short product titles dense retrieval is already strong, so it's
off by default and kept opt-in for noisier/larger catalogs (an _unproven_ claim we don't
assert on stage). ~1.2 GB, CPU-runnable.

---

## 11. Phase 2.1 Results (implemented 2026-06-13)

**Architecture (live):**

```
UserContext → profile → gte-modernbert-base embed → retrieve (cosine, all)
    → [optional: Qwen3-Reranker-0.6B cross-encoder re-score top-20]
    → business rerank (Renewed/health boost + market-aware policy) → Feed
```

Measured offline: NDCG@10 / Recall@10 / MRR on Amazon ESCI subset (500 queries, 1332 graded
judgments, English US). Reproducible via `python -m scripts.run_eval`.

**Valid eval — 50 pooled negatives/query (~55 candidates):**

| Stage      | Model                       | NDCG@10    | Recall@10  | MRR        | Notes                              |
| ---------- | --------------------------- | ---------- | ---------- | ---------- | ---------------------------------- |
| Baseline   | `bge-small-en-v1.5` (384)   | 0.4634     | **0.5275** | 0.4899     | Phase 1 (2023)                     |
| Embedder   | `gte-modernbert-base` (768) | **0.4660** | 0.5220     | **0.4938** | 2025. **+0.0026 NDCG** at ~2× size |
| + Reranker | + `Qwen3-Reranker-0.6B`     | 0.4656     | 0.4967     | 0.4935     | **Flat** vs retrieval-only         |

**Honest read:** embedder upgrade is real but marginal (bge-small a valid lighter fallback);
cross-encoder is flat even with proper pools (genuine finding, not a bug) → off by default.

**Market-aware policy (demo moment):**

| Market state                   | Nike-R score | Gap over Nike (New) | Effect                         |
| ------------------------------ | ------------ | ------------------- | ------------------------------ |
| Normal                         | 1.037        | +14.6%              | Baseline                       |
| Inventory glut (0.95)          | 1.082        | **+21.5%**          | Stronger push to clear Renewed |
| High demand + costly logistics | 0.997        | +11.9%              | Less push needed               |

Toggling market signals **visibly flips** the Renewed boost with explainable reasons.
Rule-based; LinUCB bandit is future work.

**Model choices:**

| Component       | Model                             | Released | Size    | Why                                                                |
| --------------- | --------------------------------- | -------- | ------- | ------------------------------------------------------------------ |
| Embedder        | `Alibaba-NLP/gte-modernbert-base` | 2025     | ~600 MB | ModernBERT backbone, strong MTEB, fast CPU, no auth                |
| Reranker        | `Qwen/Qwen3-Reranker-0.6B`        | Jun 2025 | ~1.2 GB | Top-tier CE, sentence-transformers native, CPU-runnable            |
| Future embedder | `google/embeddinggemma-300m`      | Sep 2025 | ~600 MB | Gated (HF auth); better on-device story. Swap when auth available. |

**Data:** ESCI subset (500 queries, 1332 judgments) cached to `data/esci/` (gitignored,
regenerable); synthetic fixtures (8 SKUs, 4 personas) as offline fallback; eval results in
`data/eval/*.json` (tracked — the evidence).

**Test coverage:** 90 base + 15 social (§12) + Phase-2.1 = **108 green**.

**Future work:** EmbeddingGemma swap once HF auth; larger ESCI (2k+); LightGBM LGBMRanker;
LinUCB bandit + OPE; FAISS/hnswlib ANN; SASRec/BERT4Rec sequential.

---

## 12. Social Media access (consent-gated social signals)

A user's connected social activity becomes another **interest-text signal** feeding the same
`profile → embed → retrieve → rerank` pipeline — no new model, no new ranking path.

### What it captures (4 signal types)

| Signal                    | Field             | Weight (repeat-count) | Why                           |
| ------------------------- | ----------------- | --------------------- | ----------------------------- |
| Follows (brands/creators) | `social.follows`  | `2×`                  | strongest, low-noise affinity |
| Likes / reactions         | `social.likes`    | `2×`                  | recent intent                 |
| Topics / hashtags         | `social.topics`   | `1×`                  | broad interest                |
| Post captions / bio       | `social.captions` | `1×`                  | richest but noisiest          |

Weights are repeat-counts (same mechanism as the 2× wishlist), in `config.SOCIAL`.

### Privacy — consent is authoritative

- **Opt-in only.** `SocialProfile.active` is `True` **only** when `consent=True` _and_ there
  is some signal. No consent → `extract_social_text` returns `""` and the feature is a
  complete no-op (verified: `consent:false` + non-empty `follows` → identical profile).
- **Mock connector**, not scraping. `social.connect(user_id, raw, consent=...)` discards
  `raw` without consent. Real OAuth connectors, data-minimization, retention controls are the
  production path — **not** built here. No credentials, no scraping.
- Consistent with the project's **on-device / privacy-preserving** thesis — a pitch strength.

### Flow & contract

```
UserContext.social ─▶ social.extract_social_text (consent-gated, weighted)
        ─▶ appended to profile.assemble_profile_text ─▶ gte-modernbert embed ─▶ ranking
```

`UserContext` gains an optional `social: SocialProfile` (consent, follows, likes, topics,
captions) — **additive + tolerant**, old payloads parse unchanged (backward-compatible
contract extension, announced to Gary per AGENTS.md). Per-item reason `"matches your social
interests"` (substring match on catalog text, also consent-gated).

### Files & tests

`recommend/social.py`, `schemas.py` (`SocialProfile`), `profile.py`, `pipeline.py`,
`config.py` (`SOCIAL`), `fixtures/users.json` (Priya/Rahul consented; Seller `consent:false`).
**15 tests** (`tests/test_social.py`): backward-compat, consent gating (both directions),
weighting, mock connector, profile integration, reason string.

### Future work

Real OAuth connectors per platform; richer interest extraction on captions; recency decay on
likes; per-signal consent granularity; on-device processing so raw social data never leaves
the client.
