"""Unit tests for the MediaStore storage module."""

import os
import shutil
import tempfile

import pytest

from app.storage.media_store import MediaStore


@pytest.fixture
def tmp_storage(tmp_path):
    """Provide a temporary directory as the storage base."""
    return tmp_path


@pytest.fixture
def store(tmp_storage):
    """Create a MediaStore instance with a temp base path."""
    return MediaStore(base_path=str(tmp_storage), uri_prefix="s3://second-life/")


class TestDirectoryCreation:
    """Test that storage directories are created on initialization."""

    def test_creates_images_directory(self, tmp_storage):
        MediaStore(base_path=str(tmp_storage))
        assert (tmp_storage / "images").is_dir()

    def test_creates_heatmaps_directory(self, tmp_storage):
        MediaStore(base_path=str(tmp_storage))
        assert (tmp_storage / "heatmaps").is_dir()

    def test_creates_frames_directory(self, tmp_storage):
        MediaStore(base_path=str(tmp_storage))
        assert (tmp_storage / "frames").is_dir()

    def test_does_not_fail_if_directories_exist(self, tmp_storage):
        (tmp_storage / "images").mkdir(parents=True)
        (tmp_storage / "heatmaps").mkdir(parents=True)
        (tmp_storage / "frames").mkdir(parents=True)
        # Should not raise
        MediaStore(base_path=str(tmp_storage))


class TestSaveImage:
    """Test saving images to storage."""

    def test_save_image_returns_uri(self, store):
        uri = store.save_image(b"fake-image-data", "product_001.jpg")
        assert uri == "s3://second-life/images/product_001.jpg"

    def test_save_image_writes_file(self, store, tmp_storage):
        store.save_image(b"image-bytes", "item.png")
        file_path = tmp_storage / "images" / "item.png"
        assert file_path.exists()
        assert file_path.read_bytes() == b"image-bytes"

    def test_save_image_overwrites_existing(self, store, tmp_storage):
        store.save_image(b"old-data", "item.jpg")
        store.save_image(b"new-data", "item.jpg")
        file_path = tmp_storage / "images" / "item.jpg"
        assert file_path.read_bytes() == b"new-data"


class TestSaveHeatmap:
    """Test saving heatmaps to storage."""

    def test_save_heatmap_returns_uri(self, store):
        uri = store.save_heatmap(b"heatmap-data", "item123_heatmap.png")
        assert uri == "s3://second-life/heatmaps/item123_heatmap.png"

    def test_save_heatmap_writes_file(self, store, tmp_storage):
        store.save_heatmap(b"heatmap-bytes", "scan.png")
        file_path = tmp_storage / "heatmaps" / "scan.png"
        assert file_path.exists()
        assert file_path.read_bytes() == b"heatmap-bytes"


class TestSaveFrame:
    """Test saving video frames to storage."""

    def test_save_frame_returns_uri(self, store):
        uri = store.save_frame(b"frame-data", "frame_001.jpg")
        assert uri == "s3://second-life/frames/frame_001.jpg"

    def test_save_frame_writes_file(self, store, tmp_storage):
        store.save_frame(b"frame-bytes", "frame_002.jpg")
        file_path = tmp_storage / "frames" / "frame_002.jpg"
        assert file_path.exists()
        assert file_path.read_bytes() == b"frame-bytes"


class TestRetrieve:
    """Test retrieving files by URI."""

    def test_retrieve_saved_image(self, store):
        store.save_image(b"img-content", "photo.jpg")
        result = store.retrieve("s3://second-life/images/photo.jpg")
        assert result == b"img-content"

    def test_retrieve_saved_heatmap(self, store):
        store.save_heatmap(b"heatmap-content", "map.png")
        result = store.retrieve("s3://second-life/heatmaps/map.png")
        assert result == b"heatmap-content"

    def test_retrieve_saved_frame(self, store):
        store.save_frame(b"frame-content", "f1.jpg")
        result = store.retrieve("s3://second-life/frames/f1.jpg")
        assert result == b"frame-content"

    def test_retrieve_nonexistent_file_returns_none(self, store):
        result = store.retrieve("s3://second-life/images/missing.jpg")
        assert result is None

    def test_retrieve_wrong_prefix_returns_none(self, store):
        store.save_image(b"data", "file.jpg")
        result = store.retrieve("s3://other-bucket/images/file.jpg")
        assert result is None


class TestGetHeatmapUri:
    """Test URI generation for heatmaps."""

    def test_generates_consistent_uri(self, store):
        uri = store.get_heatmap_uri("item_abc_heatmap.png")
        assert uri == "s3://second-life/heatmaps/item_abc_heatmap.png"

    def test_matches_saved_heatmap_uri(self, store):
        predicted_uri = store.get_heatmap_uri("scan.png")
        actual_uri = store.save_heatmap(b"data", "scan.png")
        assert predicted_uri == actual_uri


class TestConfiguration:
    """Test environment-based configuration."""

    def test_default_uri_prefix(self, tmp_storage):
        store = MediaStore(base_path=str(tmp_storage))
        uri = store.save_image(b"data", "test.jpg")
        assert uri.startswith("s3://second-life/")

    def test_custom_uri_prefix(self, tmp_storage):
        store = MediaStore(
            base_path=str(tmp_storage), uri_prefix="s3://my-bucket/"
        )
        uri = store.save_image(b"data", "test.jpg")
        assert uri == "s3://my-bucket/images/test.jpg"

    def test_uri_prefix_gets_trailing_slash(self, tmp_storage):
        store = MediaStore(
            base_path=str(tmp_storage), uri_prefix="s3://no-slash"
        )
        uri = store.save_image(b"data", "file.jpg")
        assert uri == "s3://no-slash/images/file.jpg"

    def test_env_variable_storage_path(self, tmp_storage, monkeypatch):
        env_path = str(tmp_storage / "env_storage")
        monkeypatch.setenv("STORAGE_BASE_PATH", env_path)
        store = MediaStore()
        assert store.base_path.as_posix().endswith("env_storage")
        assert (tmp_storage / "env_storage" / "images").is_dir()

    def test_env_variable_uri_prefix(self, tmp_storage, monkeypatch):
        monkeypatch.setenv("STORAGE_URI_PREFIX", "s3://env-bucket/")
        store = MediaStore(base_path=str(tmp_storage))
        uri = store.save_image(b"data", "test.jpg")
        assert uri.startswith("s3://env-bucket/")
