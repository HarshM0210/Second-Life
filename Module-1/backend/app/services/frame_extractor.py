"""
Video frame extraction utility.

Extracts evenly-spaced frames from a video file for use by the
Anomaly Detector and Wear Detector in the grading pipeline.

Server-side fallback for demo; in production, frame extraction
happens client-side.

Requirements: 3.3
"""

import cv2
import numpy as np


def extract_frames(
    video_path: str, min_frames: int = 5
) -> list[tuple[float, np.ndarray]]:
    """Extract evenly-spaced frames from a video file.

    Args:
        video_path: Path to the video file.
        min_frames: Minimum number of frames to extract (default 5).

    Returns:
        List of (timestamp_seconds, frame_image) tuples.
        Returns empty list if file not found or cannot be opened.
        Returns partial results if video is corrupt mid-stream.
    """
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        return []

    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # Handle degenerate cases
        if fps <= 0 or total_frame_count <= 0:
            # Try to read at least one frame
            ret, frame = cap.read()
            if ret:
                return [(0.0, frame)]
            return []

        duration = total_frame_count / fps

        # If video has fewer frames than min_frames, extract all available frames
        num_frames = min(min_frames, total_frame_count)

        # Calculate evenly-spaced frame indices across the video
        # For N frames from a video with F total frames:
        # indices at floor(F-1) * i / (N-1) for i in 0..N-1
        if num_frames == 1:
            frame_indices = [0]
        else:
            frame_indices = [
                int(round((total_frame_count - 1) * i / (num_frames - 1)))
                for i in range(num_frames)
            ]

        results: list[tuple[float, np.ndarray]] = []

        for frame_idx in frame_indices:
            # Seek to the frame index
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()

            if ret:
                # Calculate actual timestamp for this frame
                timestamp = frame_idx / fps
                results.append((timestamp, frame))
            # If read fails (corrupt video), continue to try remaining frames
            # This provides partial results for corrupt videos

        return results

    finally:
        cap.release()
