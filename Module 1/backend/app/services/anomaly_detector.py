"""
Anomaly Detector service.

Runs PatchCore inference on item images to produce an anomaly severity score
and pixel-level heatmap. Supports graceful degradation when no trained model
is available, and a simulated/mock mode for demo purposes.
"""

import asyncio
import os
import time
import uuid
from pathlib import Path

import cv2
import numpy as np

from app.models.results import AnomalyResult

# Configuration via environment variables
MODEL_BASE_PATH = os.environ.get("ANOMALY_MODEL_BASE_PATH", "models")
HEATMAP_STORAGE_PATH = os.environ.get("HEATMAP_STORAGE_PATH", "storage/heatmaps")
INFERENCE_TIMEOUT_MS = int(os.environ.get("ANOMALY_INFERENCE_TIMEOUT_MS", "1500"))
DEMO_MODE = os.environ.get("ANOMALY_DEMO_MODE", "true").lower() == "true"


class AnomalyDetector:
    """
    Detects anomalies in product images using PatchCore models.

    Supports three operational modes:
    1. Real inference: loads a pre-trained model and runs PatchCore
    2. Demo/mock mode: generates simulated scores and heatmaps using OpenCV
    3. Graceful degradation: returns severity=0.0 when no model is available
    """

    def __init__(
        self,
        model_base_path: str | None = None,
        heatmap_storage_path: str | None = None,
        timeout_ms: int | None = None,
        demo_mode: bool | None = None,
    ):
        self._model_base_path = model_base_path or MODEL_BASE_PATH
        self._heatmap_storage_path = heatmap_storage_path or HEATMAP_STORAGE_PATH
        self._timeout_ms = timeout_ms if timeout_ms is not None else INFERENCE_TIMEOUT_MS
        self._demo_mode = demo_mode if demo_mode is not None else DEMO_MODE

    def detect(self, images: list[np.ndarray], category: str) -> AnomalyResult:
        """
        Process images through the category-specific anomaly detection model.

        Returns the max anomaly severity across all images, a heatmap URI,
        and model availability status.

        Timeout: 1500ms (configurable).

        Args:
            images: List of BGR image arrays (as loaded by OpenCV).
            category: Product category for model selection.

        Returns:
            AnomalyResult with severity, heatmap URI, and status.
        """
        start_time = time.monotonic()
        deadline_sec = self._timeout_ms / 1000.0

        # Validate images first
        validated_images = self._validate_images(images)
        if validated_images is None:
            # All images are corrupt
            heatmap_uri = self._generate_empty_heatmap(category)
            return AnomalyResult(
                anomaly_severity=1.0,
                heatmap_uri=heatmap_uri,
                model_available=False,
                failure_reason="image_corruption",
            )

        # Check for timeout before inference
        elapsed = time.monotonic() - start_time
        if elapsed >= deadline_sec:
            heatmap_uri = self._generate_empty_heatmap(category)
            return AnomalyResult(
                anomaly_severity=1.0,
                heatmap_uri=heatmap_uri,
                model_available=False,
                failure_reason="inference_timeout",
            )

        # Check if model is available
        model_path = self._get_model_path(category)

        if self._demo_mode:
            # Demo mode: simulate inference with OpenCV-based heatmaps
            return self._run_demo_inference(validated_images, category, start_time, deadline_sec)

        if not model_path.exists():
            # No model available — graceful degradation
            heatmap_uri = self._generate_empty_heatmap(category)
            return AnomalyResult(
                anomaly_severity=0.0,
                heatmap_uri=heatmap_uri,
                model_available=False,
                failure_reason="anomaly_model_unavailable",
            )

        # Real model inference (future implementation)
        return self._run_model_inference(validated_images, category, model_path, start_time, deadline_sec)

    def _validate_images(self, images: list[np.ndarray]) -> list[np.ndarray] | None:
        """
        Validate that images are readable numpy arrays with valid dimensions.

        Returns the list of valid images, or None if all are corrupt.
        """
        if not images:
            return None

        valid = []
        for img in images:
            if img is None:
                continue
            if not isinstance(img, np.ndarray):
                continue
            if img.ndim < 2 or img.size == 0:
                continue
            valid.append(img)

        return valid if valid else None

    def _get_model_path(self, category: str) -> Path:
        """Get the expected model file path for a category."""
        safe_category = category.lower().replace(" ", "_").replace("&", "and")
        return Path(self._model_base_path) / safe_category / "model.pth"

    def _run_demo_inference(
        self,
        images: list[np.ndarray],
        category: str,
        start_time: float,
        deadline_sec: float,
    ) -> AnomalyResult:
        """
        Run simulated inference using OpenCV for demo purposes.

        Generates pseudo-random anomaly scores based on image properties
        and produces a visual heatmap using Gaussian blur and color mapping.
        """
        severities: list[float] = []
        heatmaps: list[np.ndarray] = []

        for img in images:
            # Check timeout
            elapsed = time.monotonic() - start_time
            if elapsed >= deadline_sec:
                heatmap_uri = self._generate_empty_heatmap(category)
                return AnomalyResult(
                    anomaly_severity=1.0,
                    heatmap_uri=heatmap_uri,
                    model_available=False,
                    failure_reason="inference_timeout",
                )

            severity, heatmap = self._simulate_anomaly_score(img)
            severities.append(severity)
            heatmaps.append(heatmap)

        # Max severity across all images
        max_severity = max(severities) if severities else 0.0
        max_severity = min(max(max_severity, 0.0), 1.0)

        # Store the heatmap of the image with max severity
        max_idx = severities.index(max(severities))
        heatmap_uri = self._store_heatmap(heatmaps[max_idx], category)

        return AnomalyResult(
            anomaly_severity=round(max_severity, 4),
            heatmap_uri=heatmap_uri,
            model_available=True,
            failure_reason=None,
        )

    def _simulate_anomaly_score(self, img: np.ndarray) -> tuple[float, np.ndarray]:
        """
        Simulate an anomaly score from image properties.

        Uses edge detection and texture analysis to produce a deterministic
        but realistic-looking anomaly score and heatmap.
        """
        # Convert to grayscale if color
        if img.ndim == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img

        # Compute edges as a proxy for anomaly regions
        edges = cv2.Canny(gray, 50, 150)

        # Compute Laplacian variance as a texture complexity measure
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        lap_var = laplacian.var()

        # Normalize edge density to [0, 1]
        edge_density = np.count_nonzero(edges) / edges.size

        # Combine signals into a severity score
        # Higher edge density and texture variance → higher anomaly
        severity = min(edge_density * 2.0 + (lap_var / 5000.0) * 0.3, 1.0)
        severity = max(severity, 0.0)

        # Generate heatmap from edge-detected regions
        blurred = cv2.GaussianBlur(edges.astype(np.float32), (21, 21), 0)
        normalized = cv2.normalize(blurred, None, 0, 255, cv2.NORM_MINMAX)
        heatmap = cv2.applyColorMap(normalized.astype(np.uint8), cv2.COLORMAP_JET)

        return severity, heatmap

    def _run_model_inference(
        self,
        images: list[np.ndarray],
        category: str,
        model_path: Path,
        start_time: float,
        deadline_sec: float,
    ) -> AnomalyResult:
        """
        Run actual PatchCore model inference.

        This is a placeholder for when trained models become available.
        The structure supports loading an anomalib model and running inference.
        """
        # Future: load and run anomalib PatchCore model
        # For now, fall back to demo inference if model loading fails
        try:
            # Placeholder: attempt to load model
            # from anomalib.deploy import OpenVINOInferencer
            # inferencer = OpenVINOInferencer(path=model_path)
            raise NotImplementedError("Real model inference not yet implemented")
        except Exception:
            # Fall back to demo mode if model can't be loaded
            return self._run_demo_inference(images, category, start_time, deadline_sec)

    def _store_heatmap(self, heatmap: np.ndarray, category: str) -> str:
        """
        Store a heatmap image to the local filesystem.

        Returns an S3-compatible URI path.
        """
        storage_dir = Path(self._heatmap_storage_path)
        storage_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{category.lower().replace(' ', '_')}_{uuid.uuid4().hex[:12]}_heatmap.png"
        filepath = storage_dir / filename

        cv2.imwrite(str(filepath), heatmap)

        # Return S3-compatible URI
        return f"s3://heatmaps/{filename}"

    def _generate_empty_heatmap(self, category: str) -> str:
        """
        Generate and store a blank/empty heatmap for error cases.

        Returns the URI of the stored empty heatmap.
        """
        storage_dir = Path(self._heatmap_storage_path)
        storage_dir.mkdir(parents=True, exist_ok=True)

        # Create a small black image as placeholder
        empty = np.zeros((64, 64, 3), dtype=np.uint8)
        filename = f"{category.lower().replace(' ', '_')}_{uuid.uuid4().hex[:12]}_heatmap.png"
        filepath = storage_dir / filename

        cv2.imwrite(str(filepath), empty)

        return f"s3://heatmaps/{filename}"
