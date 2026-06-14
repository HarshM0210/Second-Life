# Plan.md — The Winning Edge

This file is the *ambition layer* on top of `README.md`. README = what to build in 48h. Plan = the cutting-edge ideas that separate a top-3 finish from a competent demo. Every idea is tagged with the rubric axis it scores against and a **build cost** (🟢 buildable in 48h · 🟡 partial/mockable · 🔴 vision-only, for the pitch).

**Rubric (from the organizers):** (1) Presentation · (2) Implementation · (3) Technical Architecture · (4) Futuristic Vision.

**Core thesis to repeat in every pitch slide:** *"The system works for premium. For the long tail, it breaks. We built the intelligent bridge."* Tie every feature back to Priya, Rahul, or the Small Seller — the judges wrote those personas; using them is free points on Presentation.

---

## 0. The one idea that wins: reframe routing as a decision, not a classifier

Most teams will build "image → CNN → grade → if/else." That maxes out at "competent." The differentiator on the **Technical Architecture** and **Futuristic Vision** axes is to frame disposition as a **sequential decision under market uncertainty with delayed reward**:

- The "correct" destination for an item is never observed — you only see the payoff of the action you took (counterfactual problem). That makes supervised learning the *wrong* tool, not just a boring one.
- The same item should be routed differently depending on **current market state** (Renewed inventory glut, nearby P2P demand, scrap prices, logistics congestion). A static classifier can't do this; a market-aware policy can.

**Implementation ladder (pick by time left):**
- 🟢 **Demo:** a transparent scoring policy that *reads market state* as inputs (inventory level, nearby-buyer count, logistics cost) and visibly changes the decision when you slide those inputs. Even rule-based, *showing the decision flip live* when "Renewed inventory: HIGH" is toggled is a killer demo moment.
- 🟡 **Stretch:** a **contextual bandit** (LinUCB / neural-bandit) over the 6 actions, trained on synthetic logged data, with an exploration slider.
- 🔴 **Vision slide:** offline RL (CQL/IQL) on real logged dispositions, evaluated with **off-policy evaluation (doubly-robust)** so you prove lift before deployment without an A/B test. Say this sentence on stage; it signals senior-level system thinking.

> Pitch line: *"We don't classify returns. We run a market-aware policy that learns from the money it actually recovers."*

---

## 1. AI Grading — cutting-edge, all local

**Two co-equal build paths — the implementer chooses.** Both share the anomaly-detection front end; they differ only in how the score + justification are produced. See README "AI Grader" for full detail.

- **Option A (VLM-augmented, 🟡):** add a local quantized VLM for generated justification + open-ended reasoning. Richest output, most sparkle, **but needs a GPU and carries the highest 48h failure risk.**
- **Option B (no-VLM, classical, 🟢 — recommended default):** weighted score from anomaly severity + return-reason intent classifier (+ optional YOLO/ViT defect-typing) + template justification. CPU-fine, sub-2s, fully explainable, no labeled defects, no GPU. Lowest risk.

> Strategic note: Option B is not a "downgrade." Grading is a *closed* problem (severity + defect type + reason), so explainability beats open-ended reasoning here — and a traceable score-breakdown bar scores *better* on the Trust Layer than an opaque VLM verdict. Keep the VLM as a Futuristic-Vision roadmap item if you go with B.

| Idea | Rubric | Cost |
|---|---|---|
| **Zero-shot defect detection via anomaly models** (PatchCore/FastFlow on `anomalib`) — trained only on defect-free photos, no labeled defect dataset. The single highest-leverage technical choice: makes real CV grading *actually buildable in 48h* and produces a heatmap that looks incredible on screen. **Shared by both options.** | 2,3 | 🟢 |
| **Pixel-level anomaly heatmap overlaid on the product photo** in the UI. Judges *see* the AI working — enormous Presentation + Implementation payoff for ~zero extra effort once anomalib is running. | 1,2 | 🟢 |
| **Option A — Local quantized VLM** (Qwen2.5-VL, 4-bit GGUF) for natural-language justification + warranty reasoning. "Runs at the edge, no API, privacy-preserving" is a strong Architecture story. GPU-dependent. | 2,3 | 🟡 |
| **Option B — Transparent weighted score** (anomaly severity + return-reason intent classifier + optional defect-typing) with **template justification**. No GPU, no VLM, sub-2s, never hallucinates, fully traceable. | 2,3 | 🟢 |
| **Score-breakdown bar** (anomaly / defect / reason contributions shown as stacked bar). For Option B this is free and directly sells the Trust Layer; for Option A you fake it from the fusion weights. | 1,3 | 🟢 |
| **Calibrated confidence → human-in-the-loop fallback.** Low-confidence items get flagged for inspection instead of mis-graded. Shows you understand production ML risk, not just happy-path. | 3,4 | 🟢 |
| **Sub-2-second grading benchmark shown live** (timer in the UI). The organizers named "<2 seconds per item" — hit it on screen and call it out. Option B hits this trivially. | 1,2 | 🟢 |

---

## 2. Trust Layer — make it the emotional centerpiece

The Product Health Card is what a *buyer* sees. This is where Presentation points live.

| Idea | Rubric | Cost |
|---|---|---|
| **"Carfax for products"** framing — one phrase the judges instantly get. Condition, defect heatmap, history, warranty-left, AI confidence, all on one card. | 1,4 | 🟢 |
| **Verifiable provenance:** sign each Health Card (hash of images + grade + timestamp) so it can't be tampered with. Mock it with a simple hash/QR; pitch blockchain/DPP (Digital Product Passport) as the vision. EU Digital Product Passport regulation is real and arriving — name-drop it for Futuristic Vision. | 3,4 | 🟡 |
| **Buyer-facing confidence band** ("93% confident — Excellent") rather than a fake-precise single number. Honesty reads as sophistication. | 1 | 🟢 |

---

## 3. Smart Routing + P2P — the "intelligent bridge" made literal

| Idea | Rubric | Cost |
|---|---|---|
| **Live routing visualizer:** an item enters, and you watch it flow through Gate A (cost vs value) → Gate B (score) → final destination, with the market-state inputs editable. This *is* the bridge — animate it. | 1,2 | 🟢 |
| **Geo-aware P2P match** (Rahul → 50 nearby parents): embedding retrieval filtered by distance, shown on a small map. Directly dramatizes a persona. | 2,4 | 🟡 |
| **Escrow + A-to-Z guarantee wrapper** so P2P isn't "scary classifieds." Mock the flow; the point is the *trust wrapper*, which is Amazon's unfair advantage. | 4 | 🟢 |
| **Carbon-priced objective:** routing minimizes (lost value + cost + **carbon**), so a nearby donation can beat shipping 600km to refurb. Show the CO₂e term changing the decision. | 3,4 | 🟢 |

---

## 4. Prevention — the "best return is no return" flex

| Idea | Rubric | Cost |
|---|---|---|
| **Per-user fit profile** ("you keep size 8 in Nike, return 9") driving PDP nudges. Use their exact persona line on the slide. | 1,2 | 🟢 |
| **Return-risk score on the PDP** with a dynamic intervention — templated strings work fine (no model needed); use the local VLM/LLM only if Option A is already in the stack. | 2 | 🟢 |
| **Counterfactual framing:** "this nudge would have prevented X% of last quarter's returns." A number, even synthetic-but-labeled-synthetic, lands hard. | 1,4 | 🟢 |

---

## 5. Sustainability / Green Coin — owns the theme

| Idea | Rubric | Cost |
|---|---|---|
| **Live CO₂e + ₹ saved counter** that ticks up as items get routed in the demo. Pure Presentation candy. | 1 | 🟢 |
| **Green Coin redeemable only on Renewed** → demand-side subsidy that closes the loop. Explain the flywheel: grading creates supply → coin creates demand → more returns get a second life. | 4 | 🟢 |
| **Circularity dashboard:** % of returns kept out of landfill, displacement rate of new-product sales. This is the "Think Big" slide. | 4 | 🟡 |

---

## 6. Leverage Kiro + AWS deliberately (it's a scored criterion)

The organizers *explicitly* want to see AI-tool usage (Kiro) and AWS. Don't just use them — **show that you used them**:
- Build the React frontend and FastAPI scaffolding **in Kiro** and mention it in the demo ("scaffolded the whole return-flow UI in Kiro in ~20 min"). 🟢
- Deploy the grader on an **AWS GPU instance** (G-series, Free Tier/credits); have a fallback CPU build for the live demo in case of network issues. 🟢
- One slide: architecture diagram on AWS (S3 for media, GPU instance for grader, Lambda/API for routing, RDS Postgres). Directly scores **Technical Architecture**. 🟢

---

## 7. The 48-hour battle plan (time-boxed)

**Hour 0–4 — Foundation.** Repo + Kiro scaffold. Decide grader path (anomalib primary, YOLO/ViT fallback). Stub the routing function and data tables. Lock the demo script (3 persona stories) *now* so the build serves the story.

**Hour 4–16 — Module 1 vertical slice.** Return flow UI → frame extraction → anomalib heatmap + score → Health Card JSON → routing → disposition shown. Get one item flowing end-to-end. Protect this above everything.

**Hour 16–28 — Breadth.** Add P2P (geo match + map), Green Coin counter, the live routing visualizer with editable market state. If the Option B grader is locked and you chose to attempt the VLM, wire Option A's generated justification now *as a swap-in* — never as a replacement for a working path.

**Hour 28–40 — Polish + the three persona demos.** Priya (cost>value → not written off, routed + green coin), Rahul (P2P to nearby parent), Small Seller (auto-grade, no manual inspection, <2s timer). UX polish = direct Implementation points.

**Hour 40–46 — Deck + dry runs.** Story-first deck: Problem (their personas) → Bridge (our 5 modules) → Live demo → Architecture (AWS) → Vision (bandit/RL, Digital Product Passport, circularity flywheel). Rehearse the live demo twice; pre-record a backup video in case of network failure.

**Hour 46–48 — Buffer.** Freeze code. Backup video. Sleep if possible.

---

## 8. What will lose the hackathon (avoid)

- Spreading thin across 5 half-working modules. **One module fully working + a great story beats five stubs.** Module 1 must be real.
- A grader that needs a labeled defect dataset you don't have — that's why anomalib (defect-free-only training) is the pick.
- Reaching for a hosted multimodal API — explicitly disallowed here, and "we run it locally" is a *stronger* story anyway.
- **Betting the demo on Option A (the VLM) without a working Option B fallback.** If you attempt the VLM, get Option B working *first* and keep it as the live-demo path; swap in the VLM only once it's stable on the GPU. A grader that won't load on stage loses more points than a template justification ever would.
- Fake-precise numbers with no basis. Use synthetic data but *say* it's synthetic; calibrated honesty scores better than false confidence.
- A pitch that explains the tech before the problem. Lead with Priya/Rahul/Small Seller every single time.

---

## 9. One-line summary per axis (memorize for Q&A)

- **Presentation:** "Three people, one broken bridge — we built it."
- **Implementation:** "Real local CV grading, end-to-end, sub-2-seconds, no API."
- **Architecture:** "Market-aware routing policy on AWS, edge-deployable grader, delayed-reward learning loop."
- **Vision:** "Digital Product Passport + circularity flywheel: grading makes supply, Green Coin makes demand, the long tail finally gets a second life."
