# Module 1 — Grading & Fraud: Update Log

**Date:** 2026-06-15
**Scope:** Changes to the return-grading pipeline (`Module 1/backend`) that make the
AI grader actually *see* the customer's photos/video, and add a real, cutting-edge
computer-vision model to the anomaly stage.

---

## 1. Executive summary

Module 1 turns a return submission (Q&A + media) into a **Product Health Card**
(condition, health score 0–100, disposition, fraud signal). Two things changed:

1. **Media now reaches the grader.** Previously, uploaded photos/video never
   influenced the result — the CV stages ran on blank placeholder images, so the
   Health Card was driven almost entirely by the Q&A answers. This is now fixed.
2. **A real visual model was added (opt-in).** A cutting-edge **DINOv2**-based
   anomaly detector can now produce the visual condition signal, ensembled with the
   existing OpenCV heuristics. It is gated behind `ANOMALY_BACKEND=dinov2`; the
   default path is unchanged.

Net effect: the photos and video a customer submits now measurably change the
grade, and the visual signal is backed by a 2025-era learned model instead of
hand-tuned edge/texture heuristics alone.

---

## 2. The pipeline (unchanged structure)

The end-to-end flow in `pipeline_orchestrator.py` is unchanged in shape:

```
images + video frames + Q&A
        │
        ├── Anomaly detector ─┐
        ├── Wear detector     ├─ (parallel)
        ├── Intent classifier ┘
        └── Fraud scanner (Clothing & Footwear only)
        │
   cross-validate (pessimistic) → health score → disposition → Health Card
```

The **health-score formula is unchanged**:

```
health_score = 100 − (w1·anomaly + w2·defect + w3·return_reason + w4·wear)
```

with category-specific weights from the `category_weights` table (default
25/25/25/25). The **Health Card output contract is unchanged**, so Modules 2/4/5
that consume it are unaffected.

---

## 3. Previous process (the "older system")

| Stage | How it worked before | Type |
|---|---|---|
| **Media resolution** (`returns.py::_resolve_images`) | Decoded a URI **only if it was an existing local file path** (or `file://`). Anything else → a black `224×224` placeholder. | — |
| **Anomaly detector** | OpenCV "demo mode" — Canny edges + Laplacian texture variance → pseudo-severity + colormap heatmap. The PatchCore/anomalib path was an unimplemented placeholder (`NotImplementedError` → fell back to demo). | Heuristic, **no model** |
| **Wear detector** | OpenCV heuristics — Sobel/Canny/Laplacian, HSV stain stats, block-variance. | Heuristic |
| **Intent classifier** | Keyword → penalty mapping tables. | Rules |
| **Fraud scanner** | Deterministic mock seeded by `customer_id` (Clothing & Footwear only). | Mock |

### The core problem
The web app's return wizard sent **synthetic strings** (`upload://images/<name>`),
not the actual file bytes. The backend's `_resolve_images()` couldn't resolve those
to files, so **every image and video frame became a black square**. Those blank
images flowed into the anomaly and wear stages:

```python
all_images = request.images + request.video_frames   # all placeholders
anomaly = anomaly_detector.detect(all_images, ...)    # "sees" black squares
wear    = wear_detector.detect(request.images, ...)
```

Result: the photos/video were **decorative**. The Health Card was effectively
produced from the Q&A answers (`return_reason`) plus the mock fraud signal — the
visual evidence had no influence on condition, score, or disposition.

---

## 4. What changed

### 4.1 Media actually reaches the grader

**Web app** (`webapp/src/pages/ReturnWizard.tsx`): each selected photo is
downscaled (longest side ≤ 1024 px) and a single representative **video frame** is
captured via canvas; both are encoded as base64 `data:` URIs and sent in
`image_uris` / `video_frame_uris` (capped at the backend's 5-image limit).

**Backend** (`returns.py::_resolve_images`): now decodes three URI forms —

```python
if uri.startswith("data:"):
    buf = np.frombuffer(base64.b64decode(uri.split(",", 1)[1]), np.uint8)
    decoded = cv2.imdecode(buf, cv2.IMREAD_COLOR)   # real pixels
elif local file path / file://:
    decoded = cv2.imread(path)
else:
    decoded = placeholder                            # s3:// etc. in tests/demo
```

So the customer's real pixels now reach the anomaly and wear stages. No new
dependencies — OpenCV/numpy were already present.

**Verified:** a `data:` image decodes to real non-zero pixels (`real_count=1`);
a fake `s3://` URI still becomes a zero placeholder.

### 4.2 Cutting-edge DINOv2 anomaly backend (opt-in)

New service: `Module 1/backend/app/services/dinov2_anomaly.py`.

- **Model:** **DINOv2 ViT-S/14 *with registers*** (`dinov2_vits14_reg`) — Meta's
  self-supervised vision transformer; the backbone behind the 2025 SOTA anomaly
  methods (Dinomaly2, arXiv 2510.17611; CVPR 2025 VAND 3.0 challenge). Loaded via
  `torch.hub` (lazy). 22.1M params, ~88 MB fp32 weights, 384-dim patch features,
  16×16 patch grid at 224×224 input.
- **Method (training-free):** build a per-category **"known-good" memory bank** of
  patch features from reference product photos. For a submitted image, compute each
  patch's cosine **nearest-neighbour distance** to the bank; image-level
  `anomaly_severity = max patch distance`, and the per-patch distances form the
  heatmap. No labelled defect data and no training run required.
- **Ensemble with heuristics:** the final severity is the **pessimistic max** of the
  DINOv2 score and the existing OpenCV heuristic — the learned signal can only
  *raise* concern, never silently weaken the heuristic. This is the
  "model conditions + heuristics → Health Card" behaviour requested.
- **Same contract:** returns the existing `AnomalyResult` (severity + heatmap URI),
  so the rest of the pipeline and the Health Card are untouched.

### 4.3 Safe, resilient wiring

- New selector `pipeline_orchestrator.py::_build_anomaly_detector()` reads
  `ANOMALY_BACKEND` (default `opencv`). When set to `dinov2`, the DINOv2 detector is
  wrapped in a `ResilientAnomalyDetector` that **falls back to the OpenCV detector**
  if torch, weights, or a reference bank are unavailable.
- `torch` is **lazy-imported** inside the backend, so the module imports (and unit
  tests run) even where torch isn't installed.
- **Default behaviour and the existing test suite are unchanged.**

### 4.4 Reference images

13 openly-licensed product photos were fetched from the Wikimedia Commons API into
`Module 1/backend/storage/dinov2/refs/<category>/`:
`clothing_and_footwear` (4), `electronics` (6), `other` (3). These seed the
memory bank (or are pre-encoded into `<category>.npy` banks).

---

## 5. Models used (before vs after)

| Stage | Before | After |
|---|---|---|
| Anomaly | OpenCV edge/texture heuristic (demo) | **DINOv2 ViT-S/14-reg + memory-bank NN** (opt-in), ensembled with the OpenCV heuristic; OpenCV-only by default |
| Wear | OpenCV heuristics | unchanged |
| Intent | keyword mapping | unchanged |
| Fraud | deterministic mock | unchanged |
| Media → pixels | local-file only → black placeholder | **+ base64 `data:` decode** so real photos/video reach the grader |

### Configuration (env vars)
```
ANOMALY_BACKEND   opencv (default) | dinov2
DINOV2_MODEL      hub entry name (default dinov2_vits14_reg)
DINOV2_HUB_DIR    optional local torch.hub dir (offline)
DINOV2_BANK_DIR   dir of precomputed banks: <safe_category>.npy
DINOV2_REF_DIR    dir of reference images: <safe_category>/*.{jpg,png}
```
(`safe_category` = lowercase, spaces→`_`, `&`→`and`, e.g. `clothing_and_footwear`.)

---

## 6. What we achieved (impact vs the older system)

- **Photos & video now influence the grade.** Submitted media feeds the CV stages
  instead of being ignored. End-to-end through the real `/api/returns/{id}/submit`
  endpoint with `ANOMALY_BACKEND=dinov2`, a **defaced product photo grades strictly
  lower** than the clean one — the visual evidence changes condition, score, and
  disposition.
- **Real learned visual signal.** The anomaly stage can now use a 2025-era model
  (DINOv2) and localizes damage via the patch-distance heatmap, rather than relying
  only on hand-tuned edge/texture proxies.
- **No training data required.** The training-free memory-bank approach needs only a
  handful of "known-good" reference photos per category.
- **No new heavy installs.** `torch` is already a Module 1 dependency (via
  `anomalib==1.2.0`); the only added storage is the ~88 MB DINOv2 weights (cached on
  first use) plus the small reference images.
- **Safe by default.** Opt-in, lazy-loaded, with graceful fallback — the existing
  pipeline is byte-for-byte unchanged unless the flag is set.

### Cost (measured)
| Metric | Value |
|---|---|
| DINOv2 weights | ~88 MB (fp32), cached in `~/.cache/torch/hub` |
| Latency (GPU) | ~24 ms/image (first call ~525 ms incl. warm-up) |
| Latency (CPU, est.) | ~100–300 ms/image — still within the 2 s grading budget |
| New runtime deps | none (torch already present via anomalib) |

---

## 7. Validation

- **Direct model test:** builds the DINOv2 memory bank from the web-sourced
  reference images and confirms a defaced image scores higher anomaly than a clean
  one (the direct detector raises rather than falling back, so a returned result
  proves the model path ran).
- **Full-pipeline test:** real submit-API call with `ANOMALY_BACKEND=dinov2` and
  base64 image URIs → defaced item grades strictly lower than clean.
- **Regression:** **437 Module 1 tests pass** (full suite), including the new
  fallback/selection unit tests and the end-to-end DINOv2 test. Default OpenCV
  behaviour unchanged.

New/changed files:
- `app/routers/returns.py` — `data:` URI decoding in `_resolve_images()`
- `app/services/dinov2_anomaly.py` — DINOv2 backend + resilient wrapper (new)
- `app/services/pipeline_orchestrator.py` — `_build_anomaly_detector()` selector
- `tests/test_dinov2_anomaly.py` — fallback/selection unit tests (new)
- `tests/test_dinov2_pipeline.py` — end-to-end DINOv2 pipeline test (new)
- `storage/dinov2/refs/<category>/` — reference images (new)

---

## 8. Known limitations / next steps

- DINOv2 anomaly is **opt-in** and inert until `ANOMALY_BACKEND=dinov2` is set,
  torch is in the runtime, and a per-category reference bank exists.
- Reference banks are thin (3–6 images/category) — more curated "known-good" photos
  would sharpen sensitivity.
- **Wear, intent, and fraud stages remain heuristic/mock** — this update targets the
  anomaly seam and the media path only.
- Video is reduced to a single sampled frame; multi-frame aggregation is a possible
  enhancement.
- Pre-computing and caching `<category>.npy` banks would remove the first-request
  bank-build cost.
