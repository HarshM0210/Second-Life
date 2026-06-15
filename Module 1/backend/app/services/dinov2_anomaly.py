"""
DINOv2-backed anomaly detector (cutting-edge, training-free).

This is the optional, opt-in upgrade path for the OpenCV "demo" anomaly detector.
It uses DINOv2 (ViT-S/14 with registers) patch features and a per-category
"known-good" memory bank — the training-free approach from the CVPR 2025 VAND 3.0
challenge / Dinomaly2 line — to produce an anomaly severity + heatmap.

Design principles (so nothing in the default pipeline breaks):
  * Fully opt-in via ``ANOMALY_BACKEND=dinov2``. Default stays OpenCV.
  * ``torch`` is imported lazily, only when this backend actually runs, so the
    module can be imported (and unit-tested) without torch installed.
  * Pessimistic ENSEMBLE with the heuristic: final severity = max(model, OpenCV),
    so the learned signal augments — never silently weakens — the heuristics.
  * Graceful fallback: if torch / weights / a reference bank are unavailable, the
    ``ResilientAnomalyDetector`` wrapper falls back to the OpenCV detector.

Configuration (env vars):
  ANOMALY_BACKEND      "opencv" (default) | "dinov2"
  DINOV2_MODEL         hub entry name (default "dinov2_vits14_reg")
  DINOV2_HUB_DIR       optional local torch.hub dir (offline; source="local")
  DINOV2_BANK_DIR      dir of per-category banks: "<safe_category>.npy" (M, D)
  DINOV2_REF_DIR       fallback: "<safe_category>/*.{jpg,png}" reference images
                       from which a bank is built on first use
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import cv2
import numpy as np

from app.models.results import AnomalyResult
from app.services.anomaly_detector import AnomalyDetector

logger = logging.getLogger(__name__)

# ImageNet normalization (DINOv2 preprocessing)
_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
_INPUT = 224  # multiple of patch size 14 -> 16x16 patch grid


class DinoV2Unavailable(RuntimeError):
    """Raised when the DINOv2 backend cannot produce a real result (no torch,
    no weights, or no reference bank for the category)."""


def _safe_category(category: str) -> str:
    return category.lower().replace(" ", "_").replace("&", "and")


class DinoV2AnomalyDetector:
    """Training-free DINOv2 anomaly detector with heuristic ensemble.

    Holds a reference to the OpenCV ``AnomalyDetector`` for (a) heatmap storage
    and (b) the pessimistic ensemble partner.
    """

    def __init__(self, heuristic: AnomalyDetector | None = None) -> None:
        self._heuristic = heuristic or AnomalyDetector()
        self._model = None
        self._torch = None
        self._dev = "cpu"
        self._banks: dict[str, np.ndarray] = {}

    # -- lazy model load ----------------------------------------------------
    def _get_model(self):
        if self._model is not None:
            return self._model
        try:
            import torch  # lazy: only when this backend runs
        except Exception as e:  # noqa: BLE001
            raise DinoV2Unavailable(f"torch unavailable: {e}") from e

        torch.set_grad_enabled(False)
        name = os.environ.get("DINOV2_MODEL", "dinov2_vits14_reg")
        hub_dir = os.environ.get("DINOV2_HUB_DIR")
        try:
            if hub_dir:
                model = torch.hub.load(hub_dir, name, source="local", trust_repo=True)
            else:
                model = torch.hub.load("facebookresearch/dinov2", name, trust_repo=True)
        except Exception as e:  # noqa: BLE001
            raise DinoV2Unavailable(f"could not load DINOv2 '{name}': {e}") from e

        self._dev = "cuda" if torch.cuda.is_available() else "cpu"
        model.eval().to(self._dev)
        self._model = model
        self._torch = torch
        logger.info("dinov2_loaded model=%s device=%s", name, self._dev)
        return model

    # -- reference memory bank ---------------------------------------------
    def _get_bank(self, category: str) -> np.ndarray | None:
        key = _safe_category(category)
        if key in self._banks:
            return self._banks[key]

        # 1) precomputed bank file: <DINOV2_BANK_DIR>/<safe_category>.npy
        bank_dir = os.environ.get("DINOV2_BANK_DIR")
        if bank_dir:
            f = Path(bank_dir) / f"{key}.npy"
            if f.exists():
                bank = np.load(f).astype(np.float32)
                bank /= (np.linalg.norm(bank, axis=1, keepdims=True) + 1e-8)
                self._banks[key] = bank
                return bank

        # 2) build from reference images: <DINOV2_REF_DIR>/<safe_category>/*
        ref_dir = os.environ.get("DINOV2_REF_DIR")
        if ref_dir:
            d = Path(ref_dir) / key
            imgs: list[np.ndarray] = []
            if d.is_dir():
                for p in sorted(d.iterdir()):
                    img = cv2.imread(str(p))
                    if img is not None and img.size > 0:
                        imgs.append(img)
            if imgs:
                feats = self._features(imgs)            # (B, N, D)
                bank = feats.reshape(-1, feats.shape[-1])  # (B*N, D)
                self._banks[key] = bank
                return bank

        return None

    # -- feature extraction -------------------------------------------------
    def _features(self, images: list[np.ndarray]) -> np.ndarray:
        """Return L2-normalized patch features, shape (B, N_patches, D)."""
        model = self._get_model()
        torch = self._torch
        batch = []
        for img in images:
            if img is None or getattr(img, "size", 0) == 0:
                continue
            if img.ndim == 2:
                rgb = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
            else:
                rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            rgb = cv2.resize(rgb, (_INPUT, _INPUT))
            x = (rgb.astype(np.float32) / 255.0 - _MEAN) / _STD
            batch.append(np.transpose(x, (2, 0, 1)))
        if not batch:
            raise DinoV2Unavailable("no valid images to embed")
        t = torch.from_numpy(np.stack(batch)).to(self._dev)
        out = model.forward_features(t)
        f = out["x_norm_patchtokens"].cpu().numpy()      # (B, N, D)
        f /= (np.linalg.norm(f, axis=2, keepdims=True) + 1e-8)
        return f

    # -- public API (matches AnomalyDetector.detect) ------------------------
    def detect(self, images: list[np.ndarray], category: str) -> AnomalyResult:
        bank = self._get_bank(category)
        if bank is None:
            raise DinoV2Unavailable(f"no reference bank for category '{category}'")

        feats = self._features(images)                   # (B, N, D)
        best_sev = 0.0
        best_heat: np.ndarray | None = None
        for img_feats in feats:                          # (N, D)
            sims = img_feats @ bank.T                     # cosine (both normed)
            dist = 1.0 - sims.max(axis=1)                 # NN distance per patch
            sev = float(dist.max())
            if sev >= best_sev:
                best_sev = sev
                side = int(round(np.sqrt(len(dist))))
                best_heat = dist[: side * side].reshape(side, side)
        model_sev = max(0.0, min(1.0, best_sev))

        # Pessimistic ensemble with the OpenCV heuristic.
        heuristic = self._heuristic.detect(images, category)
        final_sev = max(model_sev, heuristic.anomaly_severity)

        heatmap_uri = heuristic.heatmap_uri
        if best_heat is not None:
            try:
                colored = self._render_heatmap(best_heat)
                heatmap_uri = self._heuristic._store_heatmap(colored, category)
            except Exception:  # noqa: BLE001 — heatmap is best-effort
                pass

        return AnomalyResult(
            anomaly_severity=round(final_sev, 4),
            heatmap_uri=heatmap_uri,
            model_available=True,
            failure_reason=None,
        )

    @staticmethod
    def _render_heatmap(grid: np.ndarray) -> np.ndarray:
        g = cv2.normalize(grid.astype(np.float32), None, 0, 255, cv2.NORM_MINMAX)
        g = cv2.resize(g.astype(np.uint8), (224, 224), interpolation=cv2.INTER_CUBIC)
        return cv2.applyColorMap(g, cv2.COLORMAP_JET)


class ResilientAnomalyDetector:
    """Try a primary detector; fall back to a secondary one on any failure.

    Used to wrap the DINOv2 backend with the OpenCV detector so the pipeline
    always gets a usable ``AnomalyResult``.
    """

    def __init__(self, primary, fallback) -> None:
        self._primary = primary
        self._fallback = fallback

    def detect(self, images, category: str) -> AnomalyResult:
        try:
            return self._primary.detect(images, category)
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "dinov2 anomaly backend unavailable (%s); falling back to OpenCV", e
            )
            return self._fallback.detect(images, category)
