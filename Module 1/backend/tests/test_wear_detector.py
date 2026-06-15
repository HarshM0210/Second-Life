"""
Unit tests for WearDetector service.

Uses synthetic numpy arrays as test images to validate wear detection logic.
Requirements: 7.1, 7.2, 7.3, 7.4, 7.5
"""

import time

import numpy as np
import pytest

from app.models.results import WearResult
from app.services.wear_detector import WearDetector


@pytest.fixture
def detector() -> WearDetector:
    return WearDetector()


# ---------------------------------------------------------------------------
# Helper functions to create synthetic test images
# ---------------------------------------------------------------------------

def _uniform_image(height: int = 200, width: int = 200, color: tuple = (128, 128, 128)) -> np.ndarray:
    """Create a uniform color image (minimal wear expected)."""
    img = np.full((height, width, 3), color, dtype=np.uint8)
    return img


def _noisy_image(height: int = 200, width: int = 200, noise_level: int = 80) -> np.ndarray:
    """Create a noisy image (simulates worn/damaged surface)."""
    rng = np.random.default_rng(42)
    img = rng.integers(128 - noise_level, 128 + noise_level, size=(height, width, 3), dtype=np.uint8)
    return img


def _image_with_edges_bottom(height: int = 200, width: int = 200) -> np.ndarray:
    """Create an image with high edge density in the bottom 30% (simulates sole wear).

    Uses horizontal lines with sharp contrast transitions to create strong Canny edges
    in the sole region while keeping the upper portion uniform.
    """
    img = np.full((height, width, 3), 180, dtype=np.uint8)
    # Add horizontal lines with gaps in bottom 30% — mimics sole tread patterns
    bottom_start = int(height * 0.7)
    for i in range(bottom_start, height):
        # Every other row is dark, creating sharp horizontal edges
        if i % 3 == 0:
            img[i, :] = [20, 20, 20]
        elif i % 3 == 1:
            img[i, :] = [200, 200, 200]
    return img


def _image_with_stains(height: int = 200, width: int = 200) -> np.ndarray:
    """Create an image with color anomalies (simulates stains)."""
    img = np.full((height, width, 3), 160, dtype=np.uint8)
    # Add a bright saturated patch (stain region)
    img[50:100, 50:100] = [30, 200, 50]  # bright green stain
    img[120:160, 80:140] = [20, 30, 200]  # bright red stain
    return img


def _image_with_scratches(height: int = 200, width: int = 200) -> np.ndarray:
    """Create an image with linear scratch patterns (simulates electronics damage)."""
    img = np.full((height, width, 3), 100, dtype=np.uint8)
    # Draw thin lines simulating scratches
    for y in range(0, height, 15):
        img[y, :] = [255, 255, 255]
    for x in range(0, width, 20):
        img[:, x] = [255, 255, 255]
    return img


def _grayscale_image(height: int = 200, width: int = 200) -> np.ndarray:
    """Create a 2D grayscale image."""
    return np.full((height, width), 128, dtype=np.uint8)


# ---------------------------------------------------------------------------
# Test: Empty images (Requirement 7.5)
# ---------------------------------------------------------------------------

class TestEmptyImages:
    def test_empty_list_returns_no_penalty(self, detector: WearDetector):
        """Empty image list → penalty=0.0, analysis_performed=False."""
        result = detector.detect([], "Clothing & Footwear")

        assert result.wear_detection_penalty == 0.0
        assert result.wear_indicators == []
        assert result.analysis_performed is False

    def test_all_invalid_images(self, detector: WearDetector):
        """All images invalid → penalty=0.0, analysis_performed=False."""
        invalid_images = [
            np.array([]),  # empty array
            np.array(5),   # scalar
        ]
        result = detector.detect(invalid_images, "Electronics")

        assert result.wear_detection_penalty == 0.0
        assert result.wear_indicators == []
        assert result.analysis_performed is False


# ---------------------------------------------------------------------------
# Test: Penalty range (Requirement 7.2)
# ---------------------------------------------------------------------------

class TestPenaltyRange:
    def test_penalty_within_bounds_uniform(self, detector: WearDetector):
        """Uniform image should produce a low penalty within [0.0, 1.0]."""
        images = [_uniform_image()]
        result = detector.detect(images, "Electronics")

        assert 0.0 <= result.wear_detection_penalty <= 1.0
        assert result.analysis_performed is True

    def test_penalty_within_bounds_noisy(self, detector: WearDetector):
        """Noisy image should produce a higher penalty but still within [0.0, 1.0]."""
        images = [_noisy_image()]
        result = detector.detect(images, "Clothing & Footwear")

        assert 0.0 <= result.wear_detection_penalty <= 1.0
        assert result.analysis_performed is True

    def test_penalty_higher_for_worn_images(self, detector: WearDetector):
        """Worn images should produce higher penalty than clean images."""
        clean_result = detector.detect([_uniform_image()], "Clothing & Footwear")
        worn_result = detector.detect([_image_with_edges_bottom()], "Clothing & Footwear")

        assert worn_result.wear_detection_penalty > clean_result.wear_detection_penalty


# ---------------------------------------------------------------------------
# Test: Category-specific detection (Requirement 7.1)
# ---------------------------------------------------------------------------

class TestCategorySpecific:
    def test_footwear_sole_wear_detection(self, detector: WearDetector):
        """Footwear category should detect sole wear from high edge density in bottom region."""
        images = [_image_with_edges_bottom()]
        result = detector.detect(images, "Clothing & Footwear")

        assert result.analysis_performed is True
        assert "sole_wear" in result.wear_indicators

    def test_clothing_fabric_stress_detection(self, detector: WearDetector):
        """Clothing category should detect fabric stress from texture variance."""
        images = [_noisy_image(noise_level=100)]
        result = detector.detect(images, "Clothing & Footwear")

        assert result.analysis_performed is True
        assert "fabric_stress" in result.wear_indicators

    def test_electronics_scratch_detection(self, detector: WearDetector):
        """Electronics category should detect scratches from directional edges."""
        images = [_image_with_scratches()]
        result = detector.detect(images, "Electronics")

        assert result.analysis_performed is True
        assert "scratch_marks" in result.wear_indicators

    def test_stain_detection_all_categories(self, detector: WearDetector):
        """Stain detection should work across all categories."""
        images = [_image_with_stains()]

        result_clothing = detector.detect(images, "Clothing & Footwear")
        result_electronics = detector.detect(images, "Electronics")
        result_other = detector.detect(images, "Other")

        assert "stains" in result_clothing.wear_indicators
        assert "stains" in result_electronics.wear_indicators
        assert "stains" in result_other.wear_indicators


# ---------------------------------------------------------------------------
# Test: Timeout enforcement (Requirement 7.4)
# ---------------------------------------------------------------------------

class TestTimeout:
    def test_completes_within_800ms(self, detector: WearDetector):
        """Processing should complete within 800ms even with multiple images."""
        images = [_noisy_image(300, 300) for _ in range(5)]

        start = time.perf_counter()
        result = detector.detect(images, "Clothing & Footwear")
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 800
        assert result.analysis_performed is True

    def test_partial_results_on_timeout(self, detector: WearDetector):
        """If timeout occurs, return partial results from processed images."""
        # Create many large images to potentially trigger timeout
        images = [_noisy_image(1000, 1000) for _ in range(50)]

        start = time.perf_counter()
        result = detector.detect(images, "Clothing & Footwear")
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Should still return a valid result even if not all images processed
        assert 0.0 <= result.wear_detection_penalty <= 1.0
        # Should not massively exceed the 800ms timeout (allow small overhead)
        assert elapsed_ms < 1200


# ---------------------------------------------------------------------------
# Test: Return type correctness
# ---------------------------------------------------------------------------

class TestResultType:
    def test_returns_wear_result(self, detector: WearDetector):
        """detect() should return a WearResult dataclass."""
        result = detector.detect([_uniform_image()], "Electronics")
        assert isinstance(result, WearResult)

    def test_wear_indicators_is_sorted_list(self, detector: WearDetector):
        """wear_indicators should be a sorted list of strings."""
        result = detector.detect([_image_with_stains()], "Clothing & Footwear")
        assert isinstance(result.wear_indicators, list)
        assert all(isinstance(i, str) for i in result.wear_indicators)
        assert result.wear_indicators == sorted(result.wear_indicators)


# ---------------------------------------------------------------------------
# Test: Grayscale image handling
# ---------------------------------------------------------------------------

class TestGrayscaleImages:
    def test_grayscale_input_handled(self, detector: WearDetector):
        """Grayscale (2D) images should be handled without error."""
        images = [_grayscale_image()]
        result = detector.detect(images, "Electronics")

        assert result.analysis_performed is True
        assert 0.0 <= result.wear_detection_penalty <= 1.0


# ---------------------------------------------------------------------------
# Test: Multiple images combination
# ---------------------------------------------------------------------------

class TestMultipleImages:
    def test_multiple_images_combined(self, detector: WearDetector):
        """Multiple images should produce a combined penalty (weighted max + mean)."""
        clean = _uniform_image()
        worn = _image_with_edges_bottom()
        images = [clean, worn]

        result = detector.detect(images, "Clothing & Footwear")

        # Should be higher than clean alone but may not equal the worn-only score
        clean_only = detector.detect([clean], "Clothing & Footwear")
        assert result.wear_detection_penalty >= clean_only.wear_detection_penalty

    def test_skips_invalid_among_valid(self, detector: WearDetector):
        """If some images are invalid, still process valid ones."""
        valid_image = _noisy_image()
        invalid_image = np.array([])  # empty

        result = detector.detect([invalid_image, valid_image], "Electronics")

        assert result.analysis_performed is True
        assert result.wear_detection_penalty > 0.0
