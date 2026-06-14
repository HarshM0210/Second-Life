"""Local CLIP zero-shot condition scoring. Lazy-loaded, graceful fallback."""
import logging
from pathlib import Path

from p2p.config import CONFIG

logger = logging.getLogger(__name__)

_FALLBACK = 50.0
_VIDEO_EXTS = {".mp4", ".avi", ".mov"}
_model = None

# Module-5/ — media_refs in listings are stored relative to this root (e.g.
# "fixtures/media/foo.jpg"), so a quote works regardless of the process CWD.
_MODULE_ROOT = Path(__file__).resolve().parent.parent


def _resolve_path(ref: str) -> str:
    """Resolve a media ref to an existing file: as-is, else relative to Module-5/."""
    p = Path(ref)
    if p.exists():
        return str(p)
    candidate = _MODULE_ROOT / ref
    return str(candidate) if candidate.exists() else ref


def is_model_loaded() -> bool:
    return _model is not None


def _load_model():
    global _model
    if _model is not None:
        return
    try:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(CONFIG.clip_model)
    except Exception as e:
        logger.warning("CLIP model load failed: %s", e)


def _extract_video_frames(path: str, k: int = 3):
    """Extract k evenly-spaced frames from a video. Returns list of PIL Images."""
    try:
        import cv2
        from PIL import Image
        cap = cv2.VideoCapture(path)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total < 1:
            cap.release()
            return []
        indices = [int(i * total / k) for i in range(k)]
        frames = []
        for idx in indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if ret:
                frames.append(Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
        cap.release()
        return frames
    except Exception as e:
        logger.warning("Video frame extraction failed for %s: %s", path, e)
        return []


def _load_images(paths: list[str]):
    """Load images from paths, extracting frames from videos. Returns PIL Images."""
    try:
        from PIL import Image
    except ImportError:
        logger.warning("PIL unavailable, returning fallback")
        return []

    images = []
    for ref in paths:
        p = _resolve_path(ref)
        ext = Path(p).suffix.lower()
        if ext in _VIDEO_EXTS:
            images.extend(_extract_video_frames(p))
        else:
            try:
                images.append(Image.open(p).convert("RGB"))
            except Exception as e:
                logger.warning("Cannot load image %s: %s", p, e)
    return images


def score_condition(image_paths: list[str]) -> float:
    """Score item condition 0-100 from images via CLIP zero-shot. Returns 50.0 on failure."""
    if not image_paths:
        return _FALLBACK

    try:
        import torch
    except ImportError:
        logger.warning("torch unavailable, returning fallback")
        return _FALLBACK

    _load_model()
    if _model is None:
        return _FALLBACK

    images = _load_images(image_paths)
    if not images:
        return _FALLBACK

    try:
        prompts = [label for label, _ in CONFIG.condition_prompts]
        scores = [s for _, s in CONFIG.condition_prompts]

        text_emb = _model.encode(prompts, convert_to_tensor=True)
        # Keep the score weights on the same device as the embeddings (CPU *or* GPU);
        # mixing devices raised a silent exception that pinned every score to the fallback.
        scores_t = torch.tensor(scores, device=text_emb.device)
        per_image_scores = []

        for img in images:
            img_emb = _model.encode(img, convert_to_tensor=True)
            sims = torch.nn.functional.cosine_similarity(img_emb.unsqueeze(0), text_emb)
            weights = torch.nn.functional.softmax(sims * 10.0, dim=0)  # temperature
            condition_score = float((weights * scores_t).sum())
            per_image_scores.append(condition_score)

        mean_score = sum(per_image_scores) / len(per_image_scores)
        worst = min(per_image_scores)
        # Penalize worst frame: 80% mean + 20% worst
        final = 0.8 * mean_score + 0.2 * worst
        return max(0.0, min(100.0, final))

    except Exception as e:
        logger.warning("CLIP scoring failed: %s", e)
        return _FALLBACK
