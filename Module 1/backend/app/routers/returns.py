"""
Returns router — API endpoints for the return grading workflow.

Provides:
- POST /api/returns/initiate — Initiate a return, validate window, get questions
- POST /api/returns/{return_id}/submit — Submit Q&A + media for grading
- POST /api/returns/{return_id}/p2p-choice — Record P2P divert choice

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.7, 2.8, 3.4, 5.1, 5.2, 12.1
"""

import json
import logging
import os
import base64
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config.database import get_db
from app.models.health_card import HealthCard
from app.services.exceptions import ServiceError
from app.services.media_validator import MediaValidator
from app.services.pipeline_orchestrator import PipelineInput, PipelineOrchestrator, PipelineError
from app.services.qa_collector import QACollector
from app.services.return_window import ReturnWindowValidator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/returns", tags=["returns"])


# ---------------------------------------------------------------------------
# Request / Response models — Return Initiation
# ---------------------------------------------------------------------------


class ReturnInitiateRequest(BaseModel):
    """Request body for POST /api/returns/initiate."""

    order_id: str
    product_id: str
    customer_id: str
    # Optional fields for demo/testing (mock order lookup)
    delivery_date: str | None = None  # ISO date string, defaults to 7 days ago
    category: str | None = None  # defaults to "Electronics"


class QuestionOut(BaseModel):
    """Serialized question for API response."""

    id: str
    text: str
    options: list[str]
    supplementary_input: dict | None = None
    conditional_display: str | None = None


class ReturnInitiateSuccessResponse(BaseModel):
    """Successful return initiation response (200)."""

    return_id: str
    eligible: bool = True
    window_days: int
    days_elapsed: int
    category: str
    questions: list[QuestionOut]


class ReturnInitiateExpiredResponse(BaseModel):
    """Return window expired response (403)."""

    return_id: None = None
    eligible: bool = False
    message: str
    expiry_date: str


# ---------------------------------------------------------------------------
# Mock order lookup (no real orders DB yet)
# ---------------------------------------------------------------------------


def _mock_get_order(
    order_id: str,
    product_id: str,
    customer_id: str,
    delivery_date_override: str | None = None,
    category_override: str | None = None,
) -> dict:
    """Simulate an order lookup. Returns category and delivery_date.

    For demo purposes:
    - If delivery_date_override is provided, use it; otherwise default to 7 days ago.
    - If category_override is provided, use it; otherwise default to "Electronics".
    """
    if delivery_date_override:
        delivery_date = date.fromisoformat(delivery_date_override)
    else:
        delivery_date = date.today() - timedelta(days=7)

    category = category_override or "Electronics"

    return {
        "order_id": order_id,
        "product_id": product_id,
        "customer_id": customer_id,
        "delivery_date": delivery_date,
        "category": category,
    }


def _resolve_images(uris: list[str]) -> tuple[list[np.ndarray], int]:
    """Decode submitted media URIs into image arrays for the grader.

    Resolves three URI forms so the wear / anomaly CV layers see real pixels:
      * ``data:image/...;base64,...`` — inline image uploaded by the web app
        (decoded via ``cv2.imdecode``).
      * a local file path (optionally ``file://``-prefixed) — decoded with
        ``cv2.imread``.
      * anything else (e.g. ``s3://...`` in tests/demo) — falls back to a neutral
        placeholder.

    Returns ``(image_arrays, real_count)`` where ``real_count`` is how many URIs
    resolved to genuine decoded images (0 means everything was a placeholder).
    """
    images: list[np.ndarray] = []
    real_count = 0
    placeholder = np.zeros((224, 224, 3), dtype=np.uint8)
    for uri in uris:
        decoded = None
        try:
            if uri.startswith("data:"):
                # Inline base64 image (data:image/jpeg;base64,...) — uploaded by the
                # web app so the CV graders see the customer's real pixels.
                b64 = uri.split(",", 1)[1] if "," in uri else ""
                if b64:
                    buf = np.frombuffer(base64.b64decode(b64), dtype=np.uint8)
                    decoded = cv2.imdecode(buf, cv2.IMREAD_COLOR)
            else:
                path = uri[7:] if uri.startswith("file://") else uri
                if path and os.path.exists(path):
                    decoded = cv2.imread(path)
        except Exception:  # noqa: BLE001 — never let media decode crash grading
            decoded = None
        if decoded is not None and getattr(decoded, "size", 0) > 0:
            images.append(decoded)
            real_count += 1
        else:
            images.append(placeholder)
    return images, real_count


# ---------------------------------------------------------------------------
# Endpoint — Initiate Return
# ---------------------------------------------------------------------------


@router.post("/initiate", status_code=200)
async def initiate_return(request: ReturnInitiateRequest):
    """Initiate a return — validates window and returns category-specific questions.

    Returns 200 with eligibility info + questions if within window.
    Returns 403 with expiry info if window expired.
    Returns 500 if a service error occurs.

    Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1
    """
    # 1. Look up order details (mock)
    order = _mock_get_order(
        order_id=request.order_id,
        product_id=request.product_id,
        customer_id=request.customer_id,
        delivery_date_override=request.delivery_date,
        category_override=request.category,
    )

    delivery_date: date = order["delivery_date"]
    category: str = order["category"]

    # 2. Validate return window
    validator = ReturnWindowValidator()
    try:
        result = await validator.validate(delivery_date, category)
    except ServiceError as exc:
        raise HTTPException(status_code=500, detail=exc.message)

    # 3. If not eligible — return 403
    if not result.eligible:
        response = ReturnInitiateExpiredResponse(
            return_id=None,
            eligible=False,
            message=result.message or "Return window expired.",
            expiry_date=result.expiry_date.isoformat(),
        )
        raise HTTPException(status_code=403, detail=response.model_dump())

    # 4. Generate return ID
    return_id = f"RET-{uuid.uuid4().hex[:12]}"

    # 5. Get category-specific questions
    qa_collector = QACollector()
    try:
        questions = qa_collector.get_questions(category)
    except ValueError:
        # Unknown category — fall back to "Other"
        questions = qa_collector.get_questions("Other")

    # 6. Persist return session in SQLite
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO returns (id, order_id, product_id, customer_id, category, delivery_date, initiated_at, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                return_id,
                request.order_id,
                request.product_id,
                request.customer_id,
                category,
                delivery_date.isoformat(),
                datetime.now(timezone.utc).isoformat(),
                "initiated",
            ),
        )
        await db.commit()
    finally:
        await db.close()

    # 7. Serialize questions
    questions_out = [
        QuestionOut(
            id=q.id,
            text=q.text,
            options=q.options,
            supplementary_input=q.supplementary_input.model_dump() if q.supplementary_input else None,
            conditional_display=q.conditional_display,
        )
        for q in questions
    ]

    return ReturnInitiateSuccessResponse(
        return_id=return_id,
        eligible=True,
        window_days=result.window_days,
        days_elapsed=result.days_elapsed,
        category=category,
        questions=questions_out,
    ).model_dump()


# ---------------------------------------------------------------------------
# Request / Response models — Submit & P2P
# ---------------------------------------------------------------------------


class CatalogMetadata(BaseModel):
    """Catalog metadata submitted with the grading request."""

    category: str
    original_price: float = Field(gt=0)
    purchase_date: str  # ISO 8601 date
    warranty_remaining_months: int = Field(ge=0)


class SubmitReturnRequest(BaseModel):
    """Request payload for POST /api/returns/{return_id}/submit."""

    qa_answers: dict[str, str]
    image_uris: list[str]
    video_frame_uris: list[str] = Field(default_factory=list)
    catalog_metadata: CatalogMetadata
    # Connected social accounts for the Social Connect fraud scan. Optional and
    # defaults to empty (graceful degradation: no accounts → no social penalty).
    connected_accounts: list[str] = Field(default_factory=list)


class SubmitReturnResponse(BaseModel):
    """Response payload for the submit endpoint."""

    health_card: dict[str, Any]
    p2p_divert_offered: bool


class P2PChoiceRequest(BaseModel):
    """Request payload for POST /api/returns/{return_id}/p2p-choice."""

    chose_p2p: bool


class P2PChoiceResponse(BaseModel):
    """Response payload for the P2P choice endpoint."""

    health_card: dict[str, Any]


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post("/{return_id}/submit", response_model=SubmitReturnResponse)
async def submit_return(return_id: str, body: SubmitReturnRequest) -> SubmitReturnResponse:
    """Submit Q&A answers and media for grading a return.

    1. Validates the return session exists in SQLite.
    2. Validates Q&A answers via QACollector.
    3. Validates media URIs (basic count check).
    4. Runs PipelineOrchestrator.execute() with inputs.
    5. Persists the Health Card and returns it.
    """
    # ------------------------------------------------------------------
    # 1. Look up return session from SQLite
    # ------------------------------------------------------------------
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, category, customer_id, status FROM returns WHERE id = ?",
            (return_id,),
        )
        row = await cursor.fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail=f"Return session '{return_id}' not found")

        category = row["category"]
        customer_id = row["customer_id"]
    except HTTPException:
        await db.close()
        raise
    except Exception as e:
        await db.close()
        logger.error("Database error looking up return %s: %s", return_id, str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

    # ------------------------------------------------------------------
    # 1b. Transition status to "grading" before pipeline execution
    # ------------------------------------------------------------------
    try:
        await db.execute(
            "UPDATE returns SET status = 'grading' WHERE id = ?",
            (return_id,),
        )
        await db.commit()
    except Exception as e:
        logger.error("Failed to set grading status for return %s: %s", return_id, str(e))
        # Non-fatal — continue with pipeline even if status update fails

    # ------------------------------------------------------------------
    # 2. Validate Q&A answers
    # ------------------------------------------------------------------
    qa_collector = QACollector()
    try:
        validation = qa_collector.validate_answers(category, body.qa_answers)
    except ValueError as e:
        await db.close()
        raise HTTPException(status_code=400, detail=str(e))

    if not validation.is_valid:
        await db.close()
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Incomplete Q&A answers",
                "missing_question_ids": validation.missing_question_ids,
            },
        )

    # ------------------------------------------------------------------
    # 3. Validate media (basic URI count check for demo)
    # ------------------------------------------------------------------
    media_validator = MediaValidator()
    # For demo, we accept URIs. Validate count constraints only.
    if len(body.image_uris) < 1:
        await db.close()
        raise HTTPException(status_code=400, detail="At least 1 image URI is required")
    if len(body.image_uris) > 5:
        await db.close()
        raise HTTPException(status_code=400, detail="Maximum 5 image URIs allowed")

    # ------------------------------------------------------------------
    # 4. Resolve media and execute pipeline
    # ------------------------------------------------------------------
    # Fix 2: decode real local images when available; non-local URIs (e.g. s3://)
    # fall back to a neutral placeholder. Q&A intent still drives condition when
    # only placeholders are present, so a placeholder no longer masquerades as a
    # pristine inspection.
    images, _real_images = _resolve_images(body.image_uris)
    video_frames, _ = _resolve_images(body.video_frame_uris)

    pipeline_input = PipelineInput(
        images=images,
        video_frames=video_frames,
        qa_answers=body.qa_answers,
        category=body.catalog_metadata.category,
        product_value=body.catalog_metadata.original_price,
        customer_id=customer_id,
        connected_accounts=body.connected_accounts,
        purchase_date=body.catalog_metadata.purchase_date,
        return_date=date.today().isoformat(),  # Fix 3: real ownership-window end
        warranty_remaining_months=body.catalog_metadata.warranty_remaining_months,
    )

    orchestrator = PipelineOrchestrator()
    result = await orchestrator.execute(pipeline_input)

    # ------------------------------------------------------------------
    # 5. Handle pipeline result
    # ------------------------------------------------------------------
    if isinstance(result, PipelineError):
        # Transition status to "error" on pipeline failure
        try:
            await db.execute(
                "UPDATE returns SET status = 'error' WHERE id = ?",
                (return_id,),
            )
            await db.commit()
        except Exception as e:
            logger.error("Failed to set error status for return %s: %s", return_id, str(e))
        finally:
            await db.close()
        raise HTTPException(
            status_code=500,
            detail={
                "message": result.message,
                "failed_component": result.failed_component,
            },
        )

    # result is a HealthCard
    health_card: HealthCard = result

    # ------------------------------------------------------------------
    # 6. Determine P2P divert offer
    # ------------------------------------------------------------------
    p2p_divert_offered = (
        health_card.fraud_signal.fraud_confidence >= 0.60
        and body.catalog_metadata.category == "Clothing & Footwear"
    )

    # ------------------------------------------------------------------
    # 7. Persist health card in SQLite
    # ------------------------------------------------------------------
    health_card_json = health_card.model_dump_json()
    health_card_id = str(uuid.uuid4())

    try:
        await db.execute(
            "INSERT INTO health_cards (id, return_id, health_card_json) VALUES (?, ?, ?)",
            (health_card_id, return_id, health_card_json),
        )

        # Update return status to "complete"
        await db.execute(
            "UPDATE returns SET status = 'complete' WHERE id = ?",
            (return_id,),
        )

        await db.commit()
    except Exception as e:
        logger.error("Failed to persist health card for return %s: %s", return_id, str(e))
        await db.close()
        raise HTTPException(status_code=500, detail="Failed to persist health card")
    finally:
        await db.close()

    # ------------------------------------------------------------------
    # 8. Return response
    # ------------------------------------------------------------------
    return SubmitReturnResponse(
        health_card=health_card.model_dump(),
        p2p_divert_offered=p2p_divert_offered,
    )


# ---------------------------------------------------------------------------
# P2P Choice Endpoint
# ---------------------------------------------------------------------------


@router.post("/{return_id}/p2p-choice", response_model=P2PChoiceResponse)
async def p2p_choice(return_id: str, body: P2PChoiceRequest) -> P2PChoiceResponse:
    """Record the customer's P2P divert choice and update the Health Card.

    Requirements: 15.1, 15.2, 15.3, 15.4, 15.5

    - If chose_p2p = True:
        source → "p2p_fraud_divert"
        fraud_signal.customer_chose_p2p → True
        fraud_signal.p2p_offered → True
    - If chose_p2p = False:
        source → "standard_return" (unchanged)
        fraud_signal.customer_chose_p2p → False
        fraud_signal.p2p_offered → True
        Add "enhanced_inspection" to disposition flags
    """
    # ------------------------------------------------------------------
    # 1. Look up existing Health Card from SQLite
    # ------------------------------------------------------------------
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, health_card_json FROM health_cards WHERE return_id = ?",
            (return_id,),
        )
        row = await cursor.fetchone()

        if row is None:
            raise HTTPException(
                status_code=404,
                detail=f"Health card not found for return '{return_id}'",
            )

        health_card_id = row["id"]
        health_card_data = json.loads(row["health_card_json"])

    except HTTPException:
        await db.close()
        raise
    except Exception as e:
        await db.close()
        logger.error("Database error looking up health card for return %s: %s", return_id, str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

    # ------------------------------------------------------------------
    # 2. Update Health Card based on P2P choice
    # ------------------------------------------------------------------
    if body.chose_p2p:
        # Customer chose P2P resale
        health_card_data["source"] = "p2p_fraud_divert"
        health_card_data["fraud_signal"]["customer_chose_p2p"] = True
        health_card_data["fraud_signal"]["p2p_offered"] = True
    else:
        # Customer chose standard return inspection
        health_card_data["source"] = "standard_return"
        health_card_data["fraud_signal"]["customer_chose_p2p"] = False
        health_card_data["fraud_signal"]["p2p_offered"] = True
        # Add enhanced_inspection flag for warehouse processing
        if "flags" not in health_card_data:
            health_card_data["flags"] = []
        if "enhanced_inspection" not in health_card_data["flags"]:
            health_card_data["flags"].append("enhanced_inspection")

    # ------------------------------------------------------------------
    # 3. Persist updated Health Card back to SQLite
    # ------------------------------------------------------------------
    updated_json = json.dumps(health_card_data)
    try:
        await db.execute(
            "UPDATE health_cards SET health_card_json = ? WHERE id = ?",
            (updated_json, health_card_id),
        )
        await db.commit()
    except Exception as e:
        logger.error("Failed to update health card for return %s: %s", return_id, str(e))
        await db.close()
        raise HTTPException(status_code=500, detail="Failed to update health card")
    finally:
        await db.close()

    # ------------------------------------------------------------------
    # 4. Return updated Health Card
    # ------------------------------------------------------------------
    return P2PChoiceResponse(health_card=health_card_data)
