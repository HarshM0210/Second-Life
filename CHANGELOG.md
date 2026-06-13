# Changelog — Module 2 (Recommend)

All notable changes to the Recommendation module. Keep entries newest-first.
Format: [Keep a Changelog](https://keepachangelog.com/). One line per change,
attribute it (Gary/Maddie/Ross), and reference the TASKS.md id (e.g. `M3`) where
it applies. Update this in the same commit as the change — not after.

## [Unreleased]

### Added
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
- _nothing yet_

### Fixed
- _nothing yet_
