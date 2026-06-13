# TASKS.md — Module 2 (Recommend)

Single source of truth for who-does-what. Statuses: `TODO` · `WIP` · `BLOCKED` ·
`DONE`. Update the status inline and log the change in `CHANGELOG.md` in the same
commit. Don't change a contract (`schemas.py`) without Gary's sign-off.

**Sequencing:** Maddie implements the module **and its baseline tests** end-to-end
first. Ross's work is **deferred to the end** — only the *extended* testing that
Maddie doesn't cover (adversarial, performance, integration-against-real-upstream,
demo hardening). Don't start Ross's block until Maddie's core is `DONE`.

---

## Gary (Lead) — ongoing

| id | task | status |
|----|------|--------|
| G1 | Freeze contracts + scaffold + fixtures | DONE |
| G2 | Review every PR for contract-fidelity & integration risk | WIP |
| G3 | Sync Health-Card field shape with Module 1 team; P2P `retrieve()` reuse with Module 5 team | TODO |
| G4 | Final integration + Definition-of-Done sign-off | TODO |

---

## Maddie (Sr Dev) — ACTIVE NOW

Implement against the frozen contracts. Small, reviewable commits. Every function
pure and independently testable. Each task includes its own baseline tests —
that's yours, not Ross's.

| id | task | status | notes |
|----|------|--------|-------|
| M1 | Replace `embedder._hash_embed` with real local `bge-small-en-v1.5` via `sentence-transformers`; keep the public signature identical; normalize embeddings | DONE | Local-only, no API. Model caches after first download. Update `requirements.txt`. |
| M2 | Precompute + cache catalog vectors at startup; confirm per-request path is embed(user)+retrieve+rerank only | DONE | Don't re-embed the catalog per request (demo-speed). |
| M3 | Enrich SKUs to real title/condition/price text in `profile.assemble_profile_text` so raw ids don't dominate the real embeddings | DONE | Resolve via `sku_text`; weight wishlist/searches over old history. |
| M4 | Tune `config.RERANK` weights against the demo cases so a >90 Renewed at a discount visibly out-ranks the equivalent new SKU | DONE | The headline behavior. Keep all weights in `config.py`. |
| M5 | Wire `service.py` to the real catalog / Health-Card source behind the same fixture-shaped loader; keep fixtures as the offline fallback | DONE | Coordinate field names with Gary (G3). |
| M6 | Add per-item reason strings beyond wishlist (e.g. "similar to past purchase", "trending in your category") | DONE | Drives the demo's "why this item" story. |
| M7 | Baseline tests for M1–M6: real-embedding smoke test, cache-hit path, profile enrichment, tuned-weight ranking assertion, service endpoint happy-path | DONE | Maddie owns happy-path + obvious-edge tests. Keep suite green. |
| M8 | Update `CHANGELOG.md` per change; flag any needed contract change to Gary before merging | ongoing | |

**Maddie's exit criteria:** real local embeddings live, headline Renewed-boost
demonstrable, `/recommend` serves real data, M7 tests green. Then hand to Ross.

---

## Ross (Jr Dev) — DEFERRED (start only after Maddie's core is DONE)

Extended testing only — the depth work offloaded from Maddie. Report pass/fail
with actual output and traces; never "looks fine". A red test is reported red.

| id | task | status | notes |
|----|------|--------|-------|
| R1 | Adversarial / fuzz inputs: malformed Health Cards, huge wishlists, unicode & empty searches, duplicate SKUs, SKU in wishlist *and* history | TODO | Must not crash; output stays schema-valid. |
| R2 | Performance: retrieval+rerank over a scaled catalog (1k–10k SKUs) stays under the demo budget; record numbers | TODO | Catch any accidental per-request re-embedding. |
| R3 | Determinism under real embeddings (fixed seeds, stable sort) across repeated runs | TODO | Re-verify after M1 lands. |
| R4 | Integration test against the real Module 1 Health-Card payload (not just fixtures) once available | TODO | Depends on G3. |
| R5 | `retrieve()` reusability contract for Module 5: standalone with arbitrary vectors + a geo-filter wrapper smoke test | TODO | Protects the P2P seam. |
| R6 | Demo hardening: the three persona feeds (Priya / Rahul / Small Seller) produce the expected headline items; snapshot them | TODO | This is what shows on stage. |
| R7 | Coverage sweep + edge-case gaps Maddie's M7 didn't reach | TODO | |

**Ross's exit criteria:** all extended suites green with recorded evidence;
persona snapshots locked; no contract or perf regressions.
