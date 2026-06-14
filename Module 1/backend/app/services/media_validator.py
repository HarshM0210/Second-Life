"""
Media validation service for image and video uploads.

Validates file metadata (format, size, count, duration) against
configured constraints before accepting media for the grading pipeline.

Requirements: 3.1, 3.2, 3.5
"""

from dataclasses import dataclass, field


# Constraints
MIN_IMAGE_COUNT = 1
MAX_IMAGE_COUNT = 5
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG"}
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

ALLOWED_VIDEO_FORMATS = {"MP4", "WebM"}
MAX_VIDEO_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
MAX_VIDEO_DURATION_SECONDS = 15.0


@dataclass
class MediaValidationResult:
    """Result of media validation."""

    accepted: bool
    rejected_reasons: list[str] = field(default_factory=list)


class MediaValidator:
    """Validates image and video upload metadata against configured constraints.

    Images: 1-5 files, JPEG/PNG format, max 10MB each.
    Video (optional): MP4/WebM format, max 50MB, max 15s duration.
    """

    def validate(
        self,
        images: list[dict],
        video: dict | None = None,
    ) -> MediaValidationResult:
        """Validate media file metadata.

        Args:
            images: List of dicts with keys 'format' (JPEG/PNG) and 'size_bytes' (int).
            video: Optional dict with keys 'format' (MP4/WebM), 'size_bytes' (int),
                   and 'duration_seconds' (float).

        Returns:
            MediaValidationResult with accepted status and any rejection reasons.
        """
        reasons: list[str] = []

        # Validate images
        reasons.extend(self._validate_images(images))

        # Validate video (optional)
        if video is not None:
            reasons.extend(self._validate_video(video))

        return MediaValidationResult(
            accepted=len(reasons) == 0,
            rejected_reasons=reasons,
        )

    def _validate_images(self, images: list[dict]) -> list[str]:
        """Validate image count, formats, and sizes."""
        reasons: list[str] = []

        # Check count
        count = len(images)
        if count < MIN_IMAGE_COUNT:
            reasons.append(
                f"At least {MIN_IMAGE_COUNT} image is required, got {count}"
            )
        elif count > MAX_IMAGE_COUNT:
            reasons.append(
                f"Maximum {MAX_IMAGE_COUNT} images allowed, got {count}"
            )

        # Check each image's format and size
        for i, img in enumerate(images):
            fmt = img.get("format", "").upper()
            if fmt not in ALLOWED_IMAGE_FORMATS:
                reasons.append(
                    f"Image {i + 1}: format '{img.get('format', '')}' not allowed, "
                    f"must be JPEG or PNG"
                )

            size = img.get("size_bytes", 0)
            if size > MAX_IMAGE_SIZE_BYTES:
                size_mb = size / (1024 * 1024)
                reasons.append(
                    f"Image {i + 1}: size {size_mb:.1f}MB exceeds maximum 10MB"
                )

        return reasons

    def _validate_video(self, video: dict) -> list[str]:
        """Validate video format, size, and duration."""
        reasons: list[str] = []

        fmt = video.get("format", "").upper()
        # Normalize webm casing for comparison
        normalized_formats = {f.upper() for f in ALLOWED_VIDEO_FORMATS}
        if fmt not in normalized_formats:
            reasons.append(
                f"Video format '{video.get('format', '')}' not allowed, "
                f"must be MP4 or WebM"
            )

        size = video.get("size_bytes", 0)
        if size > MAX_VIDEO_SIZE_BYTES:
            size_mb = size / (1024 * 1024)
            reasons.append(
                f"Video size {size_mb:.1f}MB exceeds maximum 50MB"
            )

        duration = video.get("duration_seconds", 0.0)
        if duration > MAX_VIDEO_DURATION_SECONDS:
            reasons.append(
                f"Video duration {duration:.1f}s exceeds maximum 15s"
            )

        return reasons
