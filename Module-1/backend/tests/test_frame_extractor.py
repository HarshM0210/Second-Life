"""
Unit tests for the video frame extraction utility.

Uses synthetic videos created with OpenCV for deterministic testing.
"""

import os
import tempfile

import cv2
import numpy as np
import pytest

from app.services.frame_extractor import extract_frames


def create_synthetic_video(
    path: str,
    fps: float = 30.0,
    duration_seconds: float = 5.0,
    width: int = 160,
    height: int = 120,
) -> str:
    """Create a synthetic video file for testing.

    Each frame has a unique solid color based on its frame index,
    making it possible to verify correct frame extraction.
    """
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(path, fourcc, fps, (width, height))

    total_frames = int(fps * duration_seconds)
    for i in range(total_frames):
        # Create a frame with color varying by index
        r = int((i / total_frames) * 255)
        g = int(((total_frames - i) / total_frames) * 255)
        b = 128
        frame = np.full((height, width, 3), (b, g, r), dtype=np.uint8)
        writer.write(frame)

    writer.release()
    return path


@pytest.fixture
def synthetic_video_path():
    """Create a temporary synthetic video and clean up after test."""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        path = f.name

    create_synthetic_video(path, fps=30.0, duration_seconds=5.0)
    yield path
    os.unlink(path)


@pytest.fixture
def short_video_path():
    """Create a short video with only 3 frames (fewer than min_frames)."""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        path = f.name

    create_synthetic_video(path, fps=30.0, duration_seconds=0.1)  # ~3 frames
    yield path
    os.unlink(path)


class TestExtractFrames:
    """Tests for extract_frames function."""

    def test_extracts_default_5_frames(self, synthetic_video_path):
        """Should extract exactly 5 frames by default from a normal video."""
        results = extract_frames(synthetic_video_path)

        assert len(results) == 5

    def test_returns_timestamp_frame_tuples(self, synthetic_video_path):
        """Each result should be a (timestamp, frame) tuple."""
        results = extract_frames(synthetic_video_path)

        for ts, frame in results:
            assert isinstance(ts, float)
            assert isinstance(frame, np.ndarray)
            assert frame.ndim == 3  # height x width x channels

    def test_timestamps_are_evenly_spaced(self, synthetic_video_path):
        """Timestamps should be evenly distributed across the video duration."""
        results = extract_frames(synthetic_video_path)
        timestamps = [ts for ts, _ in results]

        # First timestamp should be 0
        assert timestamps[0] == pytest.approx(0.0, abs=0.01)

        # Last timestamp should be close to the end of the video
        # For a 5s video at 30fps (150 frames), last frame is at index 149 -> 149/30 ≈ 4.97s
        assert timestamps[-1] > 4.0

        # Timestamps should be monotonically increasing
        for i in range(1, len(timestamps)):
            assert timestamps[i] > timestamps[i - 1]

        # Check approximately even spacing between consecutive timestamps
        if len(timestamps) > 2:
            intervals = [
                timestamps[i] - timestamps[i - 1]
                for i in range(1, len(timestamps))
            ]
            expected_interval = intervals[0]
            for interval in intervals:
                assert interval == pytest.approx(expected_interval, rel=0.15)

    def test_custom_min_frames(self, synthetic_video_path):
        """Should extract the requested number of frames."""
        results = extract_frames(synthetic_video_path, min_frames=10)

        assert len(results) == 10

    def test_file_not_found_returns_empty(self):
        """Should return empty list for non-existent file."""
        results = extract_frames("/nonexistent/path/video.mp4")

        assert results == []

    def test_invalid_file_returns_empty(self):
        """Should return empty list for a file that isn't a video."""
        with tempfile.NamedTemporaryFile(
            suffix=".mp4", delete=False, mode="w"
        ) as f:
            f.write("this is not a video file")
            path = f.name

        try:
            results = extract_frames(path)
            assert results == []
        finally:
            os.unlink(path)

    def test_fewer_frames_than_min_extracts_all(self, short_video_path):
        """If video has fewer frames than min_frames, extract all available."""
        results = extract_frames(short_video_path, min_frames=5)

        # Should extract whatever frames are available (fewer than 5)
        assert len(results) <= 5
        assert len(results) > 0

    def test_frame_dimensions_match_video(self, synthetic_video_path):
        """Extracted frames should have the same dimensions as the video."""
        results = extract_frames(synthetic_video_path)

        for _, frame in results:
            # Our synthetic video is 160x120
            assert frame.shape[0] == 120  # height
            assert frame.shape[1] == 160  # width
            assert frame.shape[2] == 3  # BGR channels

    def test_single_frame_video(self):
        """Should handle a video with exactly 1 frame."""
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            path = f.name

        # Create a 1-frame video
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(path, fourcc, 30.0, (160, 120))
        frame = np.full((120, 160, 3), (100, 150, 200), dtype=np.uint8)
        writer.write(frame)
        writer.release()

        try:
            results = extract_frames(path, min_frames=5)
            # Should extract the single available frame
            assert len(results) >= 1
        finally:
            os.unlink(path)

    def test_min_frames_one(self, synthetic_video_path):
        """Should work correctly when requesting just 1 frame."""
        results = extract_frames(synthetic_video_path, min_frames=1)

        assert len(results) == 1
        ts, frame = results[0]
        assert ts == pytest.approx(0.0, abs=0.01)
        assert isinstance(frame, np.ndarray)
