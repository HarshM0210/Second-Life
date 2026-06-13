import pytest
from unittest.mock import MagicMock
from recommend import embedder
from recommend.config import EMBED

def test_detect_silent_fallback():
    """
    R8: Detect silent embedder fallback.
    Verify that real model produces dense vectors.
    """
    vec = embedder.embed_text("test sentence")
    non_zero = sum(1 for x in vec if abs(x) > 1e-6)
    
    # Real model (bge-small) should be dense (384/384 non-zero usually)
    assert non_zero > EMBED.dim * 0.5

def test_validate_embedder_raises_on_fail(monkeypatch):
    """Confirm that validate_embedder raises RuntimeError if model fails."""
    def mock_get_model():
        raise RuntimeError("Model load failed!")
    
    monkeypatch.setattr(embedder, "_get_model", mock_get_model)
    
    with pytest.raises(RuntimeError) as excinfo:
        embedder.validate_embedder()
    assert "Recommendation model failed to load correctly" in str(excinfo.value)

def test_embed_text_strict_mode(monkeypatch):
    """Confirm that use_model=True forces an exception."""
    def mock_get_model():
        raise RuntimeError("Model load failed!")
    
    monkeypatch.setattr(embedder, "_get_model", mock_get_model)
    
    # default (use_model=None) should still fall back with a warning
    vec = embedder.embed_text("text")
    assert len(vec) == EMBED.dim
    
    # strict (use_model=True) should raise
    with pytest.raises(RuntimeError):
        embedder.embed_text("text", use_model=True)

def test_is_model_loaded():
    """Verify is_model_loaded reflects state."""
    # Ensure it's loaded
    embedder.embed_text("warmup")
    assert embedder.is_model_loaded() is True
