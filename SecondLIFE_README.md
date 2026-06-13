# Second Life Commerce — Implementation Guidelines

AI-powered returns, grading, and sustainable resale for the Amazon ecosystem. Goal: every returned/unused product is automatically routed to its highest-value next destination — the **"Intelligent Bridge"** for the long tail of returns that the current system writes off.

## Hackathon context (read this first — it drives every decision)

**Event:** 48-hour virtual hackathon (Amazon). Encouraged stack: AWS Free Tier + **Kiro** (AI IDE, kiro.dev).

**What they're looking for:** problem-solving · rapid prototype building · ability to leverage AI tools (Kiro) · collaboration. Plus: technical excellence (strong coding + system design) and AI fluency (build with cutting-edge AI).

**How teams are scored (the rubric — optimize for all four):**
1. **Quality of Presentation** — clarity, storytelling, communicating complex ideas simply.
2. **Quality of Implementation** — working prototype, code quality, UX polish.
3. **Technical Architecture** — scalability, design decisions, system thinking.
4. **Futuristic Vision** — roadmap beyond the hackathon, innovation, "Think Big."

**Prizes:** Winner ₹1,00,000 · 1st runner-up ₹75,000 · 2nd runner-up ₹50,000.

**The organizers' own framing of the problem** (use their language verbatim in the pitch — it signals we listened):
- The system works for premium goods. **For the long tail, it breaks.** "Millions of products. No intelligent bridge."
- Personas: *Priya* — ₹500 shoes, 600km back to warehouse, costs more to re-list than they're worth → written off (cost > value). *Rahul* — baby monitor works perfectly, won't list on classifieds (strangers, haggling), sits in a drawer; 50 parents nearby want it. *Small Seller* — 200 returns/month, all fine, manually inspects, guesses price, re-photographs on a phone → needs AI, not better logistics.

**Their named challenge — "Build the Intelligent Bridge" — maps 1:1 onto our modules:**
| Organizer pillar | Our module |
|---|---|
| AI Grading (instant, <2s/item, no manual inspection) | Module 1 |
| Smart Routing (ms decisions: resell / refurbish / P2P / donate) | Module 1 routing + **Module 5 P2P** |
| Trust Layer ("Product Health Card") | Module 1 output |
| Prevention (predict returns before they happen) | Module 3 |

We hit every pillar **and** add Green Credits — a deliberate over-delivery on the "Think Big" axis.

---

## System Overview

Central hub (`Amazon`) routes to five modules:

1. **Grading & Quality System** — grade a returned item, decide its disposition.
2. **Recommend** — surface refurbished + new products to the right buyer.
3. **Return Prevention** — predict and prevent bad-fit purchases before checkout.
4. **Sustainability Credits** — reward low-impact choices with redeemable "Green Coin."
5. **P2P Exchange** — direct buyer-to-buyer resale (Rahul's baby monitor → 50 nearby parents). *New — the organizers explicitly listed P2P; the old draft omitted it.*

Data flow at a glance:

```
Order -> Customer -> Return trigger
                        |
              [return-window check]
                        |
        +---------------+----------------+
        |                                |
  within window                     window over
  (reason + img + video)         (auto disposition by score)
        |
   AI Grader (LOCAL) -> Product Health Card -> Certified by Amazon AI
        |
   Gate A: cost vs value  ->  Gate B: health score
        |
   {return-to-seller | resell | refurbish | P2P | donate | recycle}
        |
   Recommend (match to buyer) + Green Credits issued
```

---

## Module 1 — Grading & Quality System (core, build first)

The headline module. Everything else hangs off the disposition decision. Organizer target: **condition assessment in under 2 seconds per item, no manual inspection.**

### Inputs
Collected from the customer in the return flow, during the return window:
- **Return reason** (free text)
- **Image(s)** of the item
- **Short video** (~15s) of the item
- Catalog metadata: category, original price, purchase date, warranty remaining

### AI Grader — runs LOCALLY (no third-party multimodal API)

> **Constraint (per your annotation):** no multimodal LLM API calls. The grader must be a model we run ourselves. This is also a *better* story for judges — "runs at the edge / in-warehouse, no per-call cost, privacy-preserving, deployable on AWS."

The grader produces two things: a **health score** (numeric) and a **justification** (the trust text on the Health Card). There are **two equally valid ways to build it**. The choice is left to the implementer — pick based on time, GPU availability, and appetite for risk. Both share the same anomaly-detection front end.

**Shared front end (both options):** unsupervised **anomaly detection** — **PatchCore** or **FastFlow** (the `anomalib` library) — trained only on *defect-free* reference images per category. Outputs a pixel-level anomaly heatmap + an anomaly score. This is the trick that makes either option buildable in 48h: **you don't need a labeled defect dataset**, only "good" product photos, trivially scrapeable from listings. Runs in milliseconds on CPU or GPU.

---

#### Option A — VLM-augmented (the impressive path) 🟡

Add a small **local open-weights VLM** on top of the anomaly front end — **Qwen2.5-VL-7B** (video-capable) or a distilled 2–4B VLM (DeepSeek-VL, Phi-style). It takes the frames + anomaly heatmap + return reason and emits the Health Card with a *generated* natural-language justification. Quantize to 4-bit GGUF/ONNX to fit a single AWS GPU instance.

- **Pros:** open-ended reasoning, richest justification text, strongest "cutting-edge AI" sparkle for the demo.
- **Cons:** needs a GPU; quantized VLMs are fiddly to set up under time pressure; can hallucinate; hardest to hit the <2s target reliably. **Highest 48h failure risk.**
- **Use when:** you have a stable GPU instance early, time to spare, and want maximum wow.

#### Option B — No-VLM, fully classical (the safe + explainable path) 🟢

Drop the language model entirely. Both grader jobs have non-VLM replacements that are faster, more reliable, and easier to demo.

**Scoring (no VLM):** combine numeric signals into a transparent weighted formula —
```
health_score = 100 - (w1·anomaly_severity      # from anomalib heatmap
                    +  w2·defect_penalty        # from YOLOv9/ViT defect classifier (optional)
                    +  w3·return_reason_penalty) # from a keyword/logreg intent classifier
```
- `anomaly_severity` — the anomalib score (always available, no labels needed).
- `defect_penalty` — *optional* fine-tuned **YOLOv9 / ViT** that types defects (scratch / crack / dent / stain / missing-part) in <10ms. Needs a small labeled defect set (public Kaggle/Roboflow datasets exist). If you have no dataset/time, **skip it** and lean on anomaly_severity alone.
- `return_reason_penalty` — a tiny intent classifier on the return-reason text (scikit-learn logistic regression, or even a keyword map): "broken"/"doesn't work" → functional defect → large penalty; "wrong size"/"didn't like" → cosmetic/none → no penalty. **Not an LLM.**

**Justification (no VLM):** a template engine fed by the structured outputs —
```
"{condition}. Detected: {defect_list}. {anomaly_phrase}. Functional check: {pass/fail}. Warranty: {n} months remaining."
```
→ *"Excellent. Detected: minor scratch (rear casing). No structural anomalies. Functional check: pass. Warranty: 5 months remaining."* Indistinguishable from VLM output on a slide; zero inference cost; never hallucinates; never crashes the demo.

- **Pros:** no GPU needed (CPU-fine at demo res); trivially hits sub-2s; **fully explainable** — every point of the score is traceable, which directly serves the Trust Layer pillar (show a score-breakdown bar). Fastest, most stable build.
- **Cons:** no open-ended reasoning (but grading is a *closed* problem — severity + defect type + reason — so this is rarely a real loss); slightly less "AI sparkle" on the surface.
- **Recover the sparkle:** pitch the **anomaly-detection-without-labels** trick (PatchCore trains only on good images — genuinely clever) and put VLM/multimodal-fusion in the *Futuristic Vision* roadmap instead of the live build.
- **Use when:** you want the lowest-risk path to a working, explainable, fast demo. **Recommended default for the 48h build.**

> **Leanest no-VLM path (zero labeled defects, zero GPU):** anomalib anomaly score + return-reason keyword classifier + template justification. Add YOLO defect-typing only if a dataset and time are available.

---

**Product Health Card output (identical for both options):**
```json
{
  "condition": "Excellent",
  "health_score": 70,
  "confidence": 0.93,
  "warranty_left_months": 5,
  "defects": ["minor scratch on rear casing"],
  "anomaly_heatmap_uri": "s3://.../item123_heatmap.png",
  "justification": "No functional defects detected; cosmetic wear consistent with light use."
}
```
The `justification` + heatmap doubles as the **trust artifact** shown to the next buyer — grading and the Trust Layer collapse into one output.

### Disposition routing (two gates, in sequence)

**Gate A — economics (corrected per annotation):**
- `total_processing_cost < product_value` → **Return to Seller** (worth handling through the normal channel)
- `total_processing_cost > product_value` → route by health score (resell / refurbish / donate / recycle), i.e. find the cheapest-to-realize destination instead of writing it off (this is exactly Priya's case)

`total_processing_cost` = reverse logistics + inspection + refurb labor + storage. Demo: lookup table per category.

**Gate B — health-card score:**

| Health score | Disposition |
|---|---|
| > 90 | **Resell** (as Renewed) — or **P2P** if a nearby buyer exists (Module 5) |
| > 70 | **Refurbish** then list |
| > 50 | **Donate** |
| < 50 | **Recycle** |

Refurbished items carry a sub-grade tier (like-new / better / very good / good) → each gets a **certificate** and a warranty tier. Seller-side actions on the refurb path: repair → relist → list → resale.

**Damaged-item branch:** if reason/grade flags damage → cost check → recycle if uneconomic.

### Build checklist
- [ ] Return-flow UI: reason field + image upload + video upload
- [ ] Frame extraction from video (client side, canvas)
- [ ] **Shared:** local anomaly detector (anomalib PatchCore/FastFlow) → score + heatmap
- [ ] **Pick one grader path:**
  - [ ] *Option A:* local VLM (Qwen2.5-VL quantized) → Health Card JSON + generated justification
  - [ ] *Option B:* return-reason intent classifier (logreg/keyword) + weighted score + template justification (+ optional YOLO/ViT defect-typing)
- [ ] Cost lookup table (CSV per category)
- [ ] Routing function (pure function: HealthCard + cost → disposition enum)
- [ ] Health Card render component ("Certified by Amazon AI" badge + score + heatmap). For Option B add a **score-breakdown bar** (anomaly / defect / reason contributions) — explainability sells the Trust Layer.

---

## Module 2 — Recommend

Surfaces **refurbished + new** products to buyers so the resale supply from Module 1 actually clears.

### Inputs (params)
User purchase history · search behavior · wishlist · current trends.

### Output
Ranked feed mixing refurbished and new SKUs. Novel bit: **refurbished inventory injected into the same ranking**, scored partly on the Health Card (a >90 Renewed unit at 30% off is a strong candidate).

**Prototype approach (local):** embedding-based retrieval with a **local** sentence/image embedding model (e.g. `bge-small`, CLIP for images) — no embedding API. Embed user (history/wishlist text) and items (title + condition + price), cosine-rank, boost high-score Renewed items. Small in-memory catalog is enough.

### Build checklist
- [ ] User profile assembler (history + wishlist + searches → text blob)
- [ ] Item embeddings (precompute, local model)
- [ ] Cosine retrieval + re-rank boosting high-score Renewed items
- [ ] Mixed feed UI (New / Renewed badges)

---

## Module 3 — Return Prevention

Predict return likelihood **before purchase** and intervene on the product page. Organizer line: *"Customers with your foot profile prefer size 8 in this brand. Best return = no return."*

### Inputs
Past order history (incl. prior returns) · search history → "what they actually like" · product as `[category → subcategory]`.

### Logic
Estimate return probability from (customer's historical return rate × product/category return rate × fit/preference mismatch). High risk → intervene: size guidance keyed to the customer's *fit profile* (their past kept-vs-returned sizes per brand), "people like you returned this for sizing," comparison nudge, or clarifying Q&A.

**Prototype approach (local):** a lightweight weighted scorer (or a small gradient-free rule model) → probability. For intervention copy, use the **local VLM/LLM** already in the stack, or templated strings — no external API.

### Build checklist
- [ ] Return-risk scorer (rule/weighted to start)
- [ ] Per-customer fit-profile table (brand → kept size)
- [ ] Category→subcategory taxonomy
- [ ] Intervention generator (local model or templates)
- [ ] PDP banner that fires above a risk threshold

---

## Module 4 — Sustainability Credits ("Green Coin")

Reward customers for choosing the low-impact disposition (donate locally, P2P resale, keep-with-partial-refund).

### Mechanics
- Greener disposition → earn **Green Coin** proportional to estimated CO₂e avoided (avoided shipping + avoided manufacture, per-category lookup).
- Coin redeemable for: discounts, vouchers, **Prime membership**.
- Redemption restricted to Renewed products → closes the loop, subsidizes second-hand demand.

### Build checklist
- [ ] CO₂e lookup table per category/disposition
- [ ] Credit ledger (event-sourced: action → coin granted)
- [ ] Redemption catalog (discount / voucher / Prime)
- [ ] Wallet UI

---

## Module 5 — P2P Exchange (NEW)

Directly addresses Rahul's persona and the organizers' "peer-to-peer exchange" pillar — the old draft had no P2P path.

### Mechanics
- When an item grades high (>90) **and** a high-affinity buyer exists nearby, list it as a P2P direct sale instead of routing through a fulfillment center.
- Buyer match reuses Module 2's embedding retrieval, filtered by geography (Rahul's 50 nearby parents).
- Amazon provides the trust wrapper: Health Card + A-to-Z guarantee + escrowed payment, so neither party deals with strangers/haggling.
- Item can ship buyer→buyer (or via a locker), **never touching an FC** → near-zero reverse-logistics cost and the largest CO₂e saving → biggest Green Coin reward.

### Build checklist
- [ ] "Resell instead of return" option in the return flow
- [ ] Geo-filtered buyer match (reuse Module 2 embeddings + distance)
- [ ] Escrow/guarantee mock + listing auto-generated from Health Card

---

## Suggested Demo Build Order (48h)

1. **Module 1 end to end** — return flow → local grader → Health Card → routing → disposition. Tells the whole story, shows real AI, hits the <2s grading target. *Build first, protect this at all costs.*
2. **Module 5 P2P** — small surface area, directly answers the Rahul persona, strong narrative payoff.
3. **Module 4 Green Coin** — easy bolt-on, very visual, owns the "sustainable" theme.
4. **Module 2 Recommend** — shows resale supply finding buyers (closes the loop).
5. **Module 3 Return Prevention** — if time remains; strong upstream-prevention closer.

## Tech Stack (prototype)
- **Frontend:** React (return flow, Health Card, wallet, rec feed, P2P listing). Built fast with Kiro.
- **Backend:** one lightweight service (FastAPI/Python or Node) holding routing logic, cost/CO₂e tables, ledger.
- **AI (all LOCAL — no third-party multimodal API):**
  - Defect detection: `anomalib` PatchCore/FastFlow (unsupervised, no defect labels) — *shared grader workhorse for both options*.
  - Condition reasoning — **pick one:**
    - *Option A:* local quantized VLM (Qwen2.5-VL-7B, video-capable) — needs GPU, richest output, highest risk.
    - *Option B (recommended default):* return-reason intent classifier (scikit-learn logreg/keyword) + weighted score formula + template justification; optional YOLOv9/ViT defect-typing. CPU-fine, sub-2s, fully explainable, no labeled defects required.
  - Embeddings: local `bge-small` / CLIP for Recommend + P2P match.
  - Deploy on AWS — GPU instance (G-series) needed only for Option A; Option B runs CPU-only, so the live demo has no GPU dependency.
- **Storage:** in-memory / SQLite for the demo; Postgres + S3 (object store for media) as the production path.

## Metrics to pitch
- Recovery rate per returned item (target +20–30%) — directly counters "written off."
- % returns skipping physical inspection (the cost killer — local video grading removes manual inspection; ties to the Small Seller persona).
- Return-rate reduction from prevention.
- CO₂e avoided per quarter.
- Renewed GMV growth.

## Demo-to-production gaps (state honestly — feeds the "Futuristic Vision" score)
- Local grader → larger fine-tuned VLM + confidence calibration; low-confidence items fall back to human inspection.
- Routing thresholds (90/70/50) are starting heuristics; production learns them from realized recovery value. The true "best disposition" reward only appears weeks later → this is a **delayed-reward decision problem**, not a static classifier. See Plan.md for the bandit/RL upgrade.
- Cost/CO₂e tables → real logistics + LCA data.
