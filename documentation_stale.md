# Second Life Commerce — Documentation index

Per-module model & parameter documentation now lives **inside each module folder** —
each is self-contained and outlines the models used, parameters, features, and the
"why / what-else" behind every choice.

| Module | Doc | Covers |
|---|---|---|
| **Module 2 — Recommend** | [`Module-2/documentation.md`](Module-2/documentation.md) | gte-modernbert embedder, Qwen3-Reranker (opt-in), retrieval, Renewed/health rerank, profile assembly, reasons, Phase 2.1 ESCI eval results, **Social Media access** (consent-gated social signals) |
| **Module 5 — P2P Exchange** | [`Module-5/documentation.md`](Module-5/documentation.md) | CLIP zero-shot condition scoring (dual-path), the **neural quantile-MLP** pricing model (periodic embeddings + pinball heads + conformal calibration), synthetic-data rationale, net-payout, pickup, eval results vs the GBM baseline |

Project-level material (the problem, the five-module concept, the hackathon framing,
the build plan) lives in `SecondLIFE_README.md` and `Plan.md`.

> Other modules (1 — Grading, 3 — Return Prevention, 4 — Sustainability Credits) are
> not yet implemented in this repo; their docs will follow the same per-folder pattern.
