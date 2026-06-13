# Changelog — Module 2 (Recommend)

All notable changes to the Recommendation module. Keep entries newest-first.
Format: [Keep a Changelog](https://keepachangelog.com/). One line per change,
attribute it (Gary/Maddie/Ross), and reference the TASKS.md id (e.g. `M3`) where
it applies. Update this in the same commit as the change — not after.

## [Unreleased]

### Added
- Amazon ESCI subset loader (`esci_loader.py`): 500 queries, 1332 graded judgments,
  cached to disk, synthetic fallback. — Maddie (U1)
- Offline eval harness (`eval_harness.py`): NDCG@10, Recall@k, MRR, pure numpy.
  bge-small baseline recorded: NDCG@10=0.5948. — Maddie (U2)
- Two-stage cross-encoder reranker (`cross_encoder.py`): Qwen3-Reranker-0.6B,
  lazy-loaded, opt-in via `use_cross_encoder=True`. — Maddie (U4)
- Market-aware policy layer (`policy.py`): MarketState (inventory/demand/logistics)
  modulates Renewed boost. Explainable stacked reasons. — Maddie (U5)
- Phase 2.1 upgrade test suite (`test_maddie_u6.py`): 23 tests covering ESCI loader,
  metrics, embedder, reranker, policy, retrieve purity. — Maddie (U6)
- Strict model validation `validate_embedder()` and startup guard to detect silent
  hash fallback. — Ross (R8)
- Extended test suite: adversarial/fuzzing (R1), performance scaling (R2),
  determinism (R3), `retrieve()` reusability (R5), and persona snapshots (R6). — Ross
- Coverage gap tests for boost saturation and missing health cards. — Ross (R7)
- Real local embeddings via `bge-small-en-v1.5` (sentence-transformers), lazy-loaded,
  L2-normalized, with batch encoding and hash-embed fallback for offline. — Maddie (M1)
- Batch `embed_texts()` for efficient catalog precompute. — Maddie (M1)
- Profile enrichment: Renewed SKUs annotated with condition/discount context for
  richer embeddings. — Maddie (M3)
- Per-item reason strings: "matches wishlist", "previously purchased", "similar to
  past purchase" (cosine >0.7), "trending in {category}". — Maddie (M6)
- Service env-var overrides: `RECOMMEND_CATALOG`, `RECOMMEND_HEALTH_CARDS`,
  `RECOMMEND_USERS` for real data sources with fixture fallback. — Maddie (M5)
- Baseline test suite (`test_maddie_baseline.py`): 21 tests covering real embeddings,
  precompute cache, profile enrichment, tuned weights, service loader, and reason
  strings. — Maddie (M7)
- Module skeleton: `schemas`, `retrieve` (pure core), `rerank`, `profile`,
  `pipeline`, `service` (FastAPI `GET /recommend`). — Gary
- Integration contracts frozen in `schemas.py` (Health Card / User context /
  Feed) with tolerant parsing. — Gary
- Offline deterministic hash-embed fallback so the pipeline runs without a
  model download. — Gary
- Fixtures (`catalog`, `health_cards`, `users`) for dependency-free dev. — Gary
- Test suite: 21 tests across retrieve / rerank / pipeline (all green). — Gary
- `requirements.txt` scaffolding. — Gary
  (Process docs `AGENTS.md` / `TASKS.md` are intentionally untracked — see `.gitignore`.)
- `.gitignore`: Python artifacts, ML caches, and work-defining process docs. — Gary

### Changed
- `config.py`: embedder swapped from `bge-small-en-v1.5` (384-dim) to
  `Alibaba-NLP/gte-modernbert-base` (768-dim, 2025 model). — Maddie (U3)
- `pipeline.py`: added `use_cross_encoder` flag for optional two-stage rerank;
  cross-encoder slots after retrieve(), before business rerank. — Maddie (U4)
- `rerank.py`: accepts optional `market_state` param for policy adjustment. Backward
  compatible (default neutral state = no change). — Maddie (U5)
- `schemas.py`: `HealthCard.from_dict` made more robust against malformed type
  conversions (e.g. non-numeric scores). — Ross (R1)
- `test_maddie_baseline.py`: de-flaked semantic similarity assertions with relative
  thresholds. — Ross (R10)
- `embedder.py`: replaced hash-embed stub with real `sentence-transformers` model
  (local-only, no API). Public signature unchanged. — Maddie (M1)
- `config.py`: tuned RERANK weights (`renewed_boost_weight=0.18`,
  `discount_boost_weight=0.04`, `health_score_floor=70`) so >90 Renewed at discount
  decisively out-ranks equivalent New (+14% margin). — Maddie (M4)
- `profile.py`: accepts optional `cards` param for condition/price enrichment. — Maddie (M3)
- `pipeline.py`: passes cards to profile assembler; generates rich per-item reason
  strings beyond wishlist. — Maddie (M3, M6)
- `service.py`: refactored to use `_load_json` helper with env-var override and
  fixture fallback. — Maddie (M5)
- `requirements.txt`: added `sentence-transformers`, `torch`, `fastapi`, `uvicorn`,
  `httpx`. — Maddie (M1)

### Fixed
- Silent embedder fallback bug where model load failures produced low-quality
  hash vectors without warning. — Ross (R8)
- `service.py`: replaced deprecated `@app.on_event("startup")` with a `lifespan`
  handler; added module-level `_recommender`/`_users` declarations. — Gary (review)
- `test_ross_r6.py`: snapshot test now asserts against a golden (was print-only);
  added a real `u-seller` Small Seller fixture + persona test (was an inline mock).
  — Gary (review)
- `test_ross_r2.py`: corrected malformed `sku_id` literal in perf fixtures. — Gary (review)
