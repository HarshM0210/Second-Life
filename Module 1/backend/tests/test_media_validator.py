"""Unit tests for the media validation service.

Tests cover:
- Image count validation (1-5 images required)
- Image format validation (JPEG/PNG only)
- Image size validation (max 10MB each)
- Video format validation (MP4/WebM only)
- Video size validation (max 50MB)
- Video duration validation (max 15s)
- Combined validation scenarios
- Edge cases

Requirements: 3.1, 3.2, 3.5
"""

import pytest

from app.services.media_validator import (
    MediaValidator,
    MediaValidationResult,
    MAX_IMAGE_SIZE_BYTES,
    MAX_VIDEO_SIZE_BYTES,
    MAX_VIDEO_DURATION_SECONDS,
)


@pytest.fixture
def validator():
    return MediaValidator()


def _img(fmt="JPEG", size_bytes=1_000_000):
    """Helper to create image metadata dict."""
    return {"format": fmt, "size_bytes": size_bytes}


def _video(fmt="MP4", size_bytes=10_000_000, duration_seconds=10.0):
    """Helper to create video metadata dict."""
    return {"format": fmt, "size_bytes": size_bytes, "duration_seconds": duration_seconds}


# --- Image Count Tests ---


class TestImageCount:
    def test_zero_images_rejected(self, validator):
        result = validator.validate(images=[])
        assert result.accepted is False
        assert any("At least 1 image" in r for r in result.rejected_reasons)

    def test_one_image_accepted(self, validator):
        result = validator.validate(images=[_img()])
        assert result.accepted is True
        assert result.rejected_reasons == []

    def test_five_images_accepted(self, validator):
        result = validator.validate(images=[_img() for _ in range(5)])
        assert result.accepted is True

    def test_six_images_rejected(self, validator):
        result = validator.validate(images=[_img() for _ in range(6)])
        assert result.accepted is False
        assert any("Maximum 5 images" in r for r in result.rejected_reasons)


# --- Image Format Tests ---


class TestImageFormat:
    def test_jpeg_accepted(self, validator):
        result = validator.validate(images=[_img(fmt="JPEG")])
        assert result.accepted is True

    def test_png_accepted(self, validator):
        result = validator.validate(images=[_img(fmt="PNG")])
        assert result.accepted is True

    def test_gif_rejected(self, validator):
        result = validator.validate(images=[_img(fmt="GIF")])
        assert result.accepted is False
        assert any("GIF" in r and "not allowed" in r for r in result.rejected_reasons)

    def test_bmp_rejected(self, validator):
        result = validator.validate(images=[_img(fmt="BMP")])
        assert result.accepted is False

    def test_mixed_valid_formats_accepted(self, validator):
        result = validator.validate(images=[_img(fmt="JPEG"), _img(fmt="PNG")])
        assert result.accepted is True

    def test_one_invalid_among_valid_rejected(self, validator):
        images = [_img(fmt="JPEG"), _img(fmt="TIFF"), _img(fmt="PNG")]
        result = validator.validate(images=images)
        assert result.accepted is False
        assert any("Image 2" in r for r in result.rejected_reasons)

    def test_case_insensitive_format(self, validator):
        """Format comparison should be case-insensitive."""
        result = validator.validate(images=[_img(fmt="jpeg")])
        assert result.accepted is True

        result = validator.validate(images=[_img(fmt="Png")])
        assert result.accepted is True


# --- Image Size Tests ---


class TestImageSize:
    def test_exactly_10mb_accepted(self, validator):
        result = validator.validate(images=[_img(size_bytes=MAX_IMAGE_SIZE_BYTES)])
        assert result.accepted is True

    def test_over_10mb_rejected(self, validator):
        result = validator.validate(images=[_img(size_bytes=MAX_IMAGE_SIZE_BYTES + 1)])
        assert result.accepted is False
        assert any("exceeds maximum 10MB" in r for r in result.rejected_reasons)

    def test_small_image_accepted(self, validator):
        result = validator.validate(images=[_img(size_bytes=100)])
        assert result.accepted is True

    def test_multiple_oversized_reports_each(self, validator):
        images = [
            _img(size_bytes=MAX_IMAGE_SIZE_BYTES + 1000),
            _img(size_bytes=MAX_IMAGE_SIZE_BYTES + 2000),
        ]
        result = validator.validate(images=images)
        assert result.accepted is False
        assert len([r for r in result.rejected_reasons if "exceeds" in r]) == 2


# --- Video Format Tests ---


class TestVideoFormat:
    def test_mp4_accepted(self, validator):
        result = validator.validate(images=[_img()], video=_video(fmt="MP4"))
        assert result.accepted is True

    def test_webm_accepted(self, validator):
        result = validator.validate(images=[_img()], video=_video(fmt="WebM"))
        assert result.accepted is True

    def test_avi_rejected(self, validator):
        result = validator.validate(images=[_img()], video=_video(fmt="AVI"))
        assert result.accepted is False
        assert any("AVI" in r and "not allowed" in r for r in result.rejected_reasons)

    def test_mov_rejected(self, validator):
        result = validator.validate(images=[_img()], video=_video(fmt="MOV"))
        assert result.accepted is False

    def test_case_insensitive_video_format(self, validator):
        result = validator.validate(images=[_img()], video=_video(fmt="mp4"))
        assert result.accepted is True

        result = validator.validate(images=[_img()], video=_video(fmt="webm"))
        assert result.accepted is True


# --- Video Size Tests ---


class TestVideoSize:
    def test_exactly_50mb_accepted(self, validator):
        result = validator.validate(
            images=[_img()], video=_video(size_bytes=MAX_VIDEO_SIZE_BYTES)
        )
        assert result.accepted is True

    def test_over_50mb_rejected(self, validator):
        result = validator.validate(
            images=[_img()], video=_video(size_bytes=MAX_VIDEO_SIZE_BYTES + 1)
        )
        assert result.accepted is False
        assert any("exceeds maximum 50MB" in r for r in result.rejected_reasons)


# --- Video Duration Tests ---


class TestVideoDuration:
    def test_exactly_15s_accepted(self, validator):
        result = validator.validate(
            images=[_img()], video=_video(duration_seconds=MAX_VIDEO_DURATION_SECONDS)
        )
        assert result.accepted is True

    def test_over_15s_rejected(self, validator):
        result = validator.validate(
            images=[_img()], video=_video(duration_seconds=15.1)
        )
        assert result.accepted is False
        assert any("exceeds maximum 15s" in r for r in result.rejected_reasons)

    def test_short_video_accepted(self, validator):
        result = validator.validate(
            images=[_img()], video=_video(duration_seconds=1.0)
        )
        assert result.accepted is True


# --- No Video Tests ---


class TestNoVideo:
    def test_no_video_valid_images_accepted(self, validator):
        result = validator.validate(images=[_img(), _img()])
        assert result.accepted is True
        assert result.rejected_reasons == []

    def test_video_is_optional(self, validator):
        """Video should be completely optional — no rejection for absence."""
        result = validator.validate(images=[_img()])
        assert result.accepted is True


# --- Combined Validation Tests ---


class TestCombinedValidation:
    def test_all_valid_accepted(self, validator):
        images = [_img(fmt="JPEG", size_bytes=5_000_000) for _ in range(3)]
        video = _video(fmt="MP4", size_bytes=30_000_000, duration_seconds=10.0)
        result = validator.validate(images=images, video=video)
        assert result.accepted is True
        assert result.rejected_reasons == []

    def test_multiple_violations_all_reported(self, validator):
        """Multiple issues should all be reported in rejected_reasons."""
        images = [_img(fmt="GIF", size_bytes=MAX_IMAGE_SIZE_BYTES + 1)]
        video = _video(fmt="AVI", size_bytes=MAX_VIDEO_SIZE_BYTES + 1, duration_seconds=20.0)
        result = validator.validate(images=images, video=video)
        assert result.accepted is False
        # Should have at least: format issue for image, size issue for image,
        # format issue for video, size issue for video, duration issue for video
        assert len(result.rejected_reasons) >= 4

    def test_valid_images_invalid_video_rejected(self, validator):
        result = validator.validate(
            images=[_img()],
            video=_video(duration_seconds=30.0),
        )
        assert result.accepted is False

    def test_invalid_images_valid_video_rejected(self, validator):
        result = validator.validate(
            images=[_img(fmt="BMP")],
            video=_video(),
        )
        assert result.accepted is False


# --- MediaValidationResult Dataclass Tests ---


class TestMediaValidationResult:
    def test_default_rejected_reasons_empty(self):
        result = MediaValidationResult(accepted=True)
        assert result.rejected_reasons == []

    def test_rejected_with_reasons(self):
        result = MediaValidationResult(
            accepted=False, rejected_reasons=["too large", "bad format"]
        )
        assert result.accepted is False
        assert len(result.rejected_reasons) == 2
