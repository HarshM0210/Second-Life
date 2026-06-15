"""
return_prevention/api/routes_model.py

Model management endpoints:
  - POST /api/v1/model/reload   — hot-reload the LightGBM model (internal only)
  - GET  /api/v1/model/feature-importance — return feature importance scores

Requirements: 4.5, 4.6, 4.7
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from return_prevention.config import settings
from return_prevention.core.model_registry import ModelRegistry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/model")

# ---------------------------------------------------------------------------
# Internal host allowlist — requests to the reload endpoint from hosts not in
# this list are rejected with HTTP 403.
# ---------------------------------------------------------------------------
INTERNAL_HOSTS: list[str] = settings.INTERNAL_HOSTS


@router.post("/reload")
async def reload_model(request: Request) -> JSONResponse:
    """
    Hot-reload the LightGBM model from disk.

    Protected: only accessible from hosts listed in INTERNAL_HOSTS.
    Returns 200 with model metadata on success, 500 on failure.
    """
    # ── IP allowlist check ────────────────────────────────────────────────
    client_host = request.client.host if request.client else None
    if client_host not in INTERNAL_HOSTS:
        logger.warning(
            "model_reload_forbidden client_host=%s",
            client_host,
        )
        return JSONResponse(
            status_code=403,
            content={"detail": "Forbidden: access restricted to internal hosts"},
        )

    # ── Reload the model ──────────────────────────────────────────────────
    registry = ModelRegistry()
    try:
        file_mtime = registry.reload(settings.MODEL_PATH)
    except RuntimeError as exc:
        logger.error(
            "model_reload_failed path=%s error=%s",
            settings.MODEL_PATH,
            exc,
        )
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc)},
        )

    return JSONResponse(
        status_code=200,
        content={
            "status": "reloaded",
            "model_path": settings.MODEL_PATH,
            "file_mtime": file_mtime.isoformat(),
        },
    )


@router.get("/feature-importance")
async def feature_importance() -> JSONResponse:
    """
    Return the LightGBM model's gain-based feature importance scores.

    Response contains exactly 9 keys matching FEATURE_COLS.
    """
    registry = ModelRegistry()
    try:
        importances = registry.feature_importances
    except RuntimeError as exc:
        logger.error("feature_importance_failed error=%s", exc)
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc)},
        )

    return JSONResponse(status_code=200, content=importances)
