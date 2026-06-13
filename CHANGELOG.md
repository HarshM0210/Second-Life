# Changelog — Module 2 (Recommend)

All notable changes to the Recommendation module. Keep entries newest-first.
Format: [Keep a Changelog](https://keepachangelog.com/). One line per change,
attribute it (Gary/Maddie/Ross), and reference the TASKS.md id (e.g. `M3`) where
it applies. Update this in the same commit as the change — not after.

## [Unreleased]

### Added
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
- `AGENTS.md` charter, `TASKS.md`, `requirements.txt`. — Gary

### Changed
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
- _nothing yet_
