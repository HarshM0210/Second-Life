"""
Wear Detector service.

Analyzes submitted images for category-relevant physical use evidence using
OpenCV-based heuristics. Produces a wear_detection_penalty (0.0-1.0) and a
list of detected wear indicators.

Requirements: 7.1, 7.2, 7.3, 7.4, 7.5
"""

import logging
import time
from typing import Final

import cv2
import numpy as np

from app.models.results import WearResult

logger = logging.getLogger(__name__)

# Timeout budget in seconds (Requirement 7.4: 800ms per item)
_TIMEOUT_SECONDS: Final[float] = 0.8

# Category-specific wear indicator thresholds
_SOLE_WEAR_EDGE_THRESHOLD: Final[float] = 0.15
_FABRIC_STRESS_VARIANCE_THRESHOLD: Final[float] = 0.20
_STAIN_COLOR_DEVIATION_THRESHOLD: Final[float] = 0.18
_SCRATCH_EDGE_THRESHOLD: Final[float] = 0.12
_GENERAL_WEAR_THRESHOLD: Final[float] = 0.25


class WearDetector:
    """Analyzes images for physical use evidence using OpenCV heuristics.

    Detects category-relevant wear indicators: sole wear (footwear),
    fabric stress (clothing), stains, scratch patterns (electronics),
    and general cleanliness.
    """

    def detect(self, images: list[np.ndarray], category: str) -> WearResult:
        """Category-aware wear analysis.

        Timeout: 800ms (Requirement 7.4).

        Args:
            images: List of item images as numpy arrays (BGR format).
            category: Product category (e.g., "Clothing & Footwear", "Electronics").

        Returns:
            WearResult with penalty score, indicators list, and analysis status.
        """
        # Handle empty/unavailable images (Requirement 7.5)
        if not images:
            logger.warning("No images provided for wear detection")
            return WearResult(
                wear_detection_penalty=0.0,
                wear_indicators=[],
                analysis_performed=False,
            )

        start_time = time.perf_counter()
        per_image_scores: list[float] = []
        all_indicators: set[str] = set()
        images_processed = 0

        for image in images:
            # Check timeout before processing each image
            elapsed = time.perf_counter() - start_time
            if elapsed >= _TIMEOUT_SECONDS:
                logger.warning(
                    "Wear detection timeout after %.0fms, processed %d/%d images",
                    elapsed * 1000,
                    images_processed,
                    len(images),
                )
                break

            # Validate image
            if not self._is_valid_image(image):
                logger.warning("Skipping invalid/corrupt image (index %d)", images_processed)
                continue

            # Analyze image based on category
            score, indicators = self._analyze_image(image, category)
            per_image_scores.append(score)
            all_indicators.update(indicators)
            images_processed += 1

        # If ALL images failed processing (Requirement 7.5)
        if not per_image_scores:
            logger.warning("All images failed processing in wear detection")
            return WearResult(
                wear_detection_penalty=0.0,
                wear_indicators=[],
                analysis_performed=False,
            )

        # Combine scores: weighted average with max emphasis
        # Use 0.6 * max + 0.4 * mean for final penalty
        max_score = max(per_image_scores)
        mean_score = sum(per_image_scores) / len(per_image_scores)
        penalty = 0.6 * max_score + 0.4 * mean_score

        # Clamp to [0.0, 1.0] (Requirement 7.2)
        penalty = max(0.0, min(1.0, penalty))

        return WearResult(
            wear_detection_penalty=round(penalty, 4),
            wear_indicators=sorted(all_indicators),
            analysis_performed=True,
        )

    def _is_valid_image(self, image: np.ndarray) -> bool:
        """Check if the image is a valid numpy array suitable for OpenCV processing."""
        if image is None:
            return False
        if not isinstance(image, np.ndarray):
            return False
        if image.ndim < 2:
            return False
        if image.size == 0:
            return False
        return True

    def _analyze_image(self, image: np.ndarray, category: str) -> tuple[float, list[str]]:
        """Analyze a single image for wear indicators based on category.

        Returns:
            Tuple of (wear_score 0.0-1.0, list of detected indicator names).
        """
        category_lower = category.lower()
        scores: list[float] = []
        indicators: list[str] = []

        # Convert to grayscale for edge/texture analysis
        if image.ndim == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        # Category-specific analyses (Requirement 7.1)
        if "footwear" in category_lower or "clothing & footwear" in category_lower:
            # Sole wear: analyze bottom 30% of image for edge density
            sole_score = self._detect_sole_wear(gray)
            if sole_score > _SOLE_WEAR_EDGE_THRESHOLD:
                indicators.append("sole_wear")
            scores.append(sole_score)

            # Fabric stress: texture variance analysis
            fabric_score = self._detect_fabric_stress(gray)
            if fabric_score > _FABRIC_STRESS_VARIANCE_THRESHOLD:
                indicators.append("fabric_stress")
            scores.append(fabric_score)

        elif "clothing" in category_lower:
            # Fabric stress for clothing-only items
            fabric_score = self._detect_fabric_stress(gray)
            if fabric_score > _FABRIC_STRESS_VARIANCE_THRESHOLD:
                indicators.append("fabric_stress")
            scores.append(fabric_score)

        elif "electronics" in category_lower:
            # Scratch patterns via edge detection
            scratch_score = self._detect_scratches(gray)
            if scratch_score > _SCRATCH_EDGE_THRESHOLD:
                indicators.append("scratch_marks")
            scores.append(scratch_score)

        # All categories: stain detection via color anomalies
        if image.ndim == 3:
            stain_score = self._detect_stains(image)
            if stain_score > _STAIN_COLOR_DEVIATION_THRESHOLD:
                indicators.append("stains")
            scores.append(stain_score)

        # All categories: general cleanliness from color uniformity
        general_score = self._detect_general_wear(gray)
        if general_score > _GENERAL_WEAR_THRESHOLD:
            indicators.append("general_wear")
        scores.append(general_score)

        # Combine per-analysis scores (max for this image)
        if scores:
            image_score = max(scores)
        else:
            image_score = 0.0

        return image_score, indicators

    def _detect_sole_wear(self, gray: np.ndarray) -> float:
        """Detect sole wear by analyzing edge density in the bottom 30% of the image.

        High edge density in the sole region indicates wear patterns, scratches,
        and material degradation.
        """
        h = gray.shape[0]
        bottom_region = gray[int(h * 0.7):, :]

        # Apply Canny edge detection
        edges = cv2.Canny(bottom_region, 50, 150)

        # Calculate edge density (ratio of edge pixels to total pixels)
        edge_density = np.count_nonzero(edges) / edges.size

        # Normalize to 0-1 range (typical edge density is 0.02 - 0.30)
        score = min(1.0, edge_density / 0.30)
        return score

    def _detect_fabric_stress(self, gray: np.ndarray) -> float:
        """Detect fabric stress by analyzing texture variance.

        High local variance in texture indicates pilling, stretching,
        or fabric degradation.
        """
        # Compute local standard deviation using a sliding window approach
        # Use Laplacian to capture texture irregularities
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        variance = laplacian.var()

        # Normalize: typical fabric variance ranges from 0 to ~2000
        # Higher variance = more texture irregularity = more wear
        score = min(1.0, variance / 2000.0)
        return score

    def _detect_stains(self, image: np.ndarray) -> float:
        """Detect stains by identifying color anomalies in the image.

        Stains appear as localized regions with colors deviating from
        the dominant color palette.
        """
        # Convert to HSV for better color anomaly detection
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        # Calculate mean and std of saturation channel
        saturation = hsv[:, :, 1].astype(np.float64)
        mean_sat = np.mean(saturation)
        std_sat = np.std(saturation)

        if std_sat < 1.0:
            return 0.0

        # Identify pixels that deviate significantly from mean saturation
        deviation_mask = np.abs(saturation - mean_sat) > (2.0 * std_sat)
        anomaly_ratio = np.count_nonzero(deviation_mask) / saturation.size

        # Normalize to 0-1 (typical anomaly ratio is 0.0 - 0.15)
        score = min(1.0, anomaly_ratio / 0.15)
        return score

    def _detect_scratches(self, gray: np.ndarray) -> float:
        """Detect scratch patterns using directional edge detection.

        Scratches on electronics appear as thin, directional edges
        distinct from the uniform surface.
        """
        # Apply Sobel filter for directional edge detection
        sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)

        # Combine directional edges
        magnitude = np.sqrt(sobel_x**2 + sobel_y**2)

        # Threshold for significant edges
        threshold = np.mean(magnitude) + 2 * np.std(magnitude)
        strong_edges = magnitude > threshold

        # Edge pixel ratio indicates scratch presence
        edge_ratio = np.count_nonzero(strong_edges) / magnitude.size

        # Normalize (typical scratch ratio is 0.0 - 0.08)
        score = min(1.0, edge_ratio / 0.08)
        return score

    def _detect_general_wear(self, gray: np.ndarray) -> float:
        """Detect general wear from color uniformity degradation.

        Worn items tend to have less uniform surface appearance due to
        accumulated micro-damage, dust, and surface degradation.
        """
        # Divide image into blocks and compute variance of block means
        h, w = gray.shape[:2]
        block_size = max(1, min(h, w) // 8)

        if block_size < 2:
            return 0.0

        block_means: list[float] = []
        for i in range(0, h - block_size + 1, block_size):
            for j in range(0, w - block_size + 1, block_size):
                block = gray[i:i + block_size, j:j + block_size]
                block_means.append(float(np.mean(block)))

        if len(block_means) < 4:
            return 0.0

        # Coefficient of variation of block means
        mean_val = np.mean(block_means)
        if mean_val < 1.0:
            return 0.0

        cv = np.std(block_means) / mean_val

        # Normalize (typical CV range for uniformity is 0.0 - 0.5)
        score = min(1.0, cv / 0.5)
        return score
