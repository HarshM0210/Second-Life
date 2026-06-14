"""Unit tests for AnomalyDetector service."""

import os
import shutil
import time
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
import pytest

from app.models.results import AnomalyResult
from app.services.anomaly_detector import AnomalyDetector

TEST_HEATMAP_DIR = "test_heatmaps"
TEST_MODEL_DIR = "test_models"


@pytest.fixture(autouse=True)
def cleanup_dirs():
    """Clean up test directories before and after each test."""
    for d in [TEST_HEATMAP_DIR, TEST_MODEL_DIR]:
        if os.path.exists(d):
            shutil.rmtree(d)
    yield
    for d in [TEST_HEATMAP_DIR, TEST_MODEL_DIR]:
        if os.path.exists(d):
            shutil.rmtree(d)


@pytest.fixture
def detector():
    """Create an AnomalyDetector in demo mode with test paths."""
    return AnomalyDetector(
        model_base_path=TEST_MODEL_DIR,
        heatmap_storage_path=TEST_HEATMAP_DIR,
        timeout_ms=1500,
        demo_mode=True,
    )


@pytest.fixture
def detector_no_demo():
    """Create an AnomalyDetector NOT in demo mode with test paths."""
    return AnomalyDetector(
        model_base_path=TEST_MODEL_DIR,
        heatmap_storage_path=TEST_HEATMAP_DIR,
        timeout_ms=1500,
        demo_mode=False,
    )


@pytest.fixture
def sample_image():
    """Create a simple test image (100x100 BGR)."""
    return np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)


@pytest.fixture
def sample_images(sample_image):
    """Create a list of test images."""
    img2 = np.random.randint(0, 255, (80, 120, 3), dtype=np.uint8)
    return [sample_image, img2]


# --- Basic Demo Mode Tests ---


def test_detect_returns_anomaly_result(detector, sample_images):
    """detect() returns an AnomalyResult dataclass."""
    result = detector.detect(sample_images, "Electronics")
    assert isinstance(result, AnomalyResult)


def test_demo_mode_model_available(detector, sample_images):
    """In demo mode, model_available is True."""
    result = detector.detect(sample_images, "Electronics")
    assert result.model_available is True
    assert result.failure_reason is None


def test_severity_in_valid_range(detector, sample_images):
    """Anomaly severity is between 0.0 and 1.0."""
    result = detector.detect(sample_images, "Electronics")
    assert 0.0 <= result.anomaly_severity <= 1.0


def test_heatmap_uri_format(detector, sample_images):
    """Heatmap URI follows S3-compatible format."""
    result = detector.detect(sample_images, "Electronics")
    assert result.heatmap_uri.startswith("s3://heatmaps/")
    assert result.heatmap_uri.endswith("_heatmap.png")


def test_heatmap_file_created(detector, sample_images):
    """Heatmap PNG file is actually written to disk."""
    result = detector.detect(sample_images, "Electronics")
    # Extract filename from URI
    filename = result.heatmap_uri.split("/")[-1]
    filepath = Path(TEST_HEATMAP_DIR) / filename
    assert filepath.exists()


def test_max_severity_across_images(detector):
    """Severity is the max across all images."""
    # Create images with different properties
    # A solid black image should have low severity (few edges)
    low_img = np.zeros((100, 100, 3), dtype=np.uint8)
    # An image with many edges should have higher severity
    high_img = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)

    result_combined = detector.detect([low_img, high_img], "Electronics")
    result_low_only = detector.detect([low_img], "Electronics")

    # Max across [low, high] should be >= low alone
    assert result_combined.anomaly_severity >= result_low_only.anomaly_severity


# --- No Model Available (Non-Demo Mode) ---


def test_no_model_graceful_degradation(detector_no_demo, sample_images):
    """When model file doesn't exist, returns severity=0.0 with failure_reason."""
    result = detector_no_demo.detect(sample_images, "Electronics")
    assert result.anomaly_severity == 0.0
    assert result.model_available is False
    assert result.failure_reason == "anomaly_model_unavailable"


def test_no_model_heatmap_still_stored(detector_no_demo, sample_images):
    """Even without a model, a placeholder heatmap URI is returned."""
    result = detector_no_demo.detect(sample_images, "Electronics")
    assert result.heatmap_uri.startswith("s3://heatmaps/")
    filename = result.heatmap_uri.split("/")[-1]
    filepath = Path(TEST_HEATMAP_DIR) / filename
    assert filepath.exists()


# --- Image Corruption Tests ---


def test_empty_image_list_is_corruption(detector):
    """Empty image list is treated as image corruption."""
    result = detector.detect([], "Electronics")
    assert result.anomaly_severity == 1.0
    assert result.failure_reason == "image_corruption"


def test_none_images_corruption(detector):
    """List of None values treated as image corruption."""
    result = detector.detect([None, None], "Electronics")
    assert result.anomaly_severity == 1.0
    assert result.failure_reason == "image_corruption"


def test_invalid_ndarray_corruption(detector):
    """Array with zero dimensions is treated as corruption."""
    empty_arr = np.array([])
    result = detector.detect([empty_arr], "Electronics")
    assert result.anomaly_severity == 1.0
    assert result.failure_reason == "image_corruption"


def test_mixed_valid_and_invalid_images(detector):
    """If some images are valid, process the valid ones (not corruption)."""
    valid_img = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
    result = detector.detect([None, valid_img, None], "Electronics")
    # Should NOT be image_corruption since one image is valid
    assert result.failure_reason is None
    assert 0.0 <= result.anomaly_severity <= 1.0


# --- Timeout Tests ---


def test_timeout_returns_severity_1(sample_images):
    """When timeout is exceeded, returns severity=1.0 with timeout reason."""
    # Use an extremely short timeout to force timeout
    detector = AnomalyDetector(
        model_base_path=TEST_MODEL_DIR,
        heatmap_storage_path=TEST_HEATMAP_DIR,
        timeout_ms=0,  # 0ms timeout - will always time out
        demo_mode=True,
    )
    result = detector.detect(sample_images, "Electronics")
    assert result.anomaly_severity == 1.0
    assert result.failure_reason == "inference_timeout"


# --- Category Handling ---


def test_different_categories_use_different_model_paths(detector_no_demo):
    """Different categories produce results (model path differs per category)."""
    result1 = detector_no_demo.detect(
        [np.zeros((50, 50, 3), dtype=np.uint8)], "Electronics"
    )
    result2 = detector_no_demo.detect(
        [np.zeros((50, 50, 3), dtype=np.uint8)], "Clothing & Footwear"
    )
    # Both should gracefully degrade (no models exist)
    assert result1.failure_reason == "anomaly_model_unavailable"
    assert result2.failure_reason == "anomaly_model_unavailable"


def test_category_in_heatmap_uri(detector, sample_images):
    """Heatmap URI contains the category name."""
    result = detector.detect(sample_images, "Electronics")
    assert "electronics" in result.heatmap_uri


# --- Grayscale Image Support ---


def test_grayscale_image_works(detector):
    """Grayscale (2D) images are processed without error."""
    gray_img = np.random.randint(0, 255, (100, 100), dtype=np.uint8)
    result = detector.detect([gray_img], "Electronics")
    assert isinstance(result, AnomalyResult)
    assert 0.0 <= result.anomaly_severity <= 1.0
    assert result.failure_reason is None


# --- Single Image ---


def test_single_image(detector):
    """Single image works correctly."""
    img = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)
    result = detector.detect([img], "Electronics")
    assert isinstance(result, AnomalyResult)
    assert 0.0 <= result.anomaly_severity <= 1.0
