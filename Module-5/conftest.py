"""Shared fixtures for Module 5 tests."""
import pytest
from unittest.mock import patch


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "real_clip: run against the real CLIP model instead of the mock "
        "(skips itself if torch/sentence-transformers/model are unavailable).",
    )


@pytest.fixture(autouse=True)
def mock_clip(request):
    """Mock CLIP scoring globally so no model download is needed.

    Tests marked @pytest.mark.real_clip opt out and exercise the real path.
    """
    if "real_clip" in request.keywords:
        yield
        return
    with patch("p2p.media.score_condition", return_value=75.0):
        yield
