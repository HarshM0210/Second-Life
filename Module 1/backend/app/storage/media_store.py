"""
Media storage module for images, video frames, and heatmaps.

Uses local filesystem for demo; interface compatible with S3.
Configuration via environment variables:
- STORAGE_BASE_PATH: Local directory for storage (default: "storage/")
- STORAGE_URI_PREFIX: URI prefix for stored files (default: "s3://second-life/")
"""

import os
from pathlib import Path


# Sub-directories for different media types
_IMAGES_DIR = "images"
_HEATMAPS_DIR = "heatmaps"
_FRAMES_DIR = "frames"


class MediaStore:
    """S3-compatible local filesystem media store.

    Stores images, video frames, and heatmaps on the local filesystem
    and returns URIs in S3-compatible format for use in the Health Card.
    """

    def __init__(
        self,
        base_path: str | None = None,
        uri_prefix: str | None = None,
    ):
        self.base_path = Path(
            base_path or os.environ.get("STORAGE_BASE_PATH", "storage/")
        )
        self.uri_prefix = (
            uri_prefix or os.environ.get("STORAGE_URI_PREFIX", "s3://second-life/")
        )
        # Ensure the URI prefix ends with a slash
        if not self.uri_prefix.endswith("/"):
            self.uri_prefix += "/"
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Create storage directories if they don't exist."""
        for subdir in (_IMAGES_DIR, _HEATMAPS_DIR, _FRAMES_DIR):
            (self.base_path / subdir).mkdir(parents=True, exist_ok=True)

    def save_image(self, image_data: bytes, filename: str) -> str:
        """Save an image and return its URI.

        Args:
            image_data: Raw image bytes.
            filename: Filename for the stored image.

        Returns:
            S3-compatible URI string.
        """
        file_path = self.base_path / _IMAGES_DIR / filename
        file_path.write_bytes(image_data)
        return f"{self.uri_prefix}{_IMAGES_DIR}/{filename}"

    def save_heatmap(self, heatmap_data: bytes, filename: str) -> str:
        """Save an anomaly heatmap and return its URI.

        Args:
            heatmap_data: Raw heatmap image bytes.
            filename: Filename for the stored heatmap.

        Returns:
            S3-compatible URI string (used in Health Card anomaly_heatmap_uri).
        """
        file_path = self.base_path / _HEATMAPS_DIR / filename
        file_path.write_bytes(heatmap_data)
        return f"{self.uri_prefix}{_HEATMAPS_DIR}/{filename}"

    def save_frame(self, frame_data: bytes, filename: str) -> str:
        """Save a video frame and return its URI.

        Args:
            frame_data: Raw frame image bytes.
            filename: Filename for the stored frame.

        Returns:
            S3-compatible URI string.
        """
        file_path = self.base_path / _FRAMES_DIR / filename
        file_path.write_bytes(frame_data)
        return f"{self.uri_prefix}{_FRAMES_DIR}/{filename}"

    def retrieve(self, uri: str) -> bytes | None:
        """Retrieve file contents by URI.

        Args:
            uri: S3-compatible URI previously returned by a save method.

        Returns:
            File bytes if found, None otherwise.
        """
        relative_path = self._uri_to_relative_path(uri)
        if relative_path is None:
            return None
        file_path = self.base_path / relative_path
        if not file_path.exists():
            return None
        return file_path.read_bytes()

    def get_heatmap_uri(self, filename: str) -> str:
        """Generate a consistent URI for a heatmap without saving.

        Useful for constructing the anomaly_heatmap_uri field
        in the Health Card before the heatmap is stored.

        Args:
            filename: Heatmap filename.

        Returns:
            S3-compatible URI string.
        """
        return f"{self.uri_prefix}{_HEATMAPS_DIR}/{filename}"

    def _uri_to_relative_path(self, uri: str) -> str | None:
        """Convert an S3-compatible URI to a relative filesystem path.

        Returns None if the URI doesn't match the configured prefix.
        """
        if not uri.startswith(self.uri_prefix):
            return None
        return uri[len(self.uri_prefix):]
