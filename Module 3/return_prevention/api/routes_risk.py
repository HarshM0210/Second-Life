"""
return_prevention/api/routes_risk.py

POST /api/v1/risk-score endpoint.

Assembles features, scores with LightGBM, generates intervention copy when
risk exceeds the configured threshold, and emits a purchase_avoidance event
as a non-blocking background task.

Requirements: 1.1, 1.7, 1.8, 1.9, 5.1–5.3, 8.3, 8.5
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from return_prevention.config import settings
from return_prevention.core.feature_assembler import FeatureAssembler
from return_prevention.core.intervention import InterventionGenerator
from return_prevention.core.scorer import score as risk_score_fn
from return_prevention.db.database import get_db
from return_prevention.db.repositories import FitProfileRepository
from return_prevention.integrations.green_coin import GreenCoinEmitter
from return_prevention.schemas.events import PurchaseAvoidanceEvent
from return_prevention.schemas.risk import RiskScoreRequest, RiskScoreResponse
from return_prevention.taxonomy.taxonomy_loader import get_taxonomy

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["risk"])

# ---------------------------------------------------------------------------
# Session deduplication — in-memory set of (customer_id, product_id, session_id)
# Prevents duplicate purchase_avoidance events within the same session.
# ---------------------------------------------------------------------------
_emitted_sessions: set[tuple[str, str, str]] = set()


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

def _get_feature_assembler() -> FeatureAssembler:
    """Dependency: provides a FeatureAssembler instance."""
    return FeatureAssembler()


def _get_green_coin_emitter() -> GreenCoinEmitter:
    """Dependency: provides a GreenCoinEmitter instance."""
    return GreenCoinEmitter()


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.post("/risk-score", response_model=RiskScoreResponse)
async def compute_risk_score(
    request: RiskScoreRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    assembler: FeatureAssembler = Depends(_get_feature_assembler),
    emitter: GreenCoinEmitter = Depends(_get_green_coin_emitter),
) -> Any:
    """
    Compute a return-risk score for a customer–product pair.

    - Validates request via Pydantic (422 on missing/invalid fields).
    - Assembles feature vector; on taxonomy miss returns early with score 0.0.
    - Scores with LightGBM model.
    - If score > RISK_THRESHOLD: selects intervention type and generates copy.
    - Emits purchase_avoidance event as a background task (session-deduplicated).
    - Returns 503 on any internal/DB failure.
    """
    try:
        # Step 1: Assemble features
        feature_vector, taxonomy_miss = await assembler.assemble(request, db)

        if taxonomy_miss:
            return RiskScoreResponse(
                risk_score=0.0,
                intervention_type=None,
                intervention_copy=None,
                taxonomy_miss=True,
            )

        # Step 2: Score
        risk_score = risk_score_fn(feature_vector)

        # Step 3: Intervention (only if above threshold)
        intervention_type = None
        intervention_copy = None

        if risk_score > settings.RISK_THRESHOLD:
            # Resolve taxonomy context for intervention selection
            taxonomy = get_taxonomy()
            product_id = request.product_id
            taxonomy_entry = taxonomy.get(product_id) if taxonomy else None

            subcategory = taxonomy_entry.subcategory if taxonomy_entry else ""
            category = taxonomy_entry.category if taxonomy_entry else ""
            brand = product_id  # In prototype, product_id maps to subcategory/brand

            # Select intervention type
            intervention_type = InterventionGenerator.select_type(
                customer_id=request.customer_id,
                brand=brand,
                subcategory=subcategory,
                category=category,
                fit_profile_repo=FitProfileRepository,
                taxonomy=taxonomy,
                db=db,
            )

            # Generate copy with context
            context_dict: dict[str, Any] = {
                "brand": brand,
                "subcategory": subcategory,
                "category": category,
                "prior_order_count": FitProfileRepository.count(
                    db, request.customer_id, brand
                ),
            }

            # Add taxonomy return rate for social proof
            if taxonomy_entry:
                context_dict["return_rate_pct"] = round(
                    taxonomy_entry.category_return_rate * 100
                )

            intervention_copy = InterventionGenerator.generate_copy(
                intervention_type=intervention_type,
                context_dict=context_dict,
            )

        # Step 4: Emit purchase_avoidance event as background task
        # Use a generated session_id for deduplication within this request context
        session_id = str(uuid.uuid4())
        dedup_key = (request.customer_id, request.product_id, session_id)

        if dedup_key not in _emitted_sessions and risk_score > settings.RISK_THRESHOLD:
            _emitted_sessions.add(dedup_key)

            event = PurchaseAvoidanceEvent(
                customer_id=request.customer_id,
                product_id=request.product_id,
                risk_score=risk_score,
                intervention_type=intervention_type.value if intervention_type else None,
                session_id=session_id,
                emitted_at=datetime.now(timezone.utc),
            )
            background_tasks.add_task(emitter.emit, event)

        # Step 5: Return response
        return RiskScoreResponse(
            risk_score=risk_score,
            intervention_type=intervention_type,
            intervention_copy=intervention_copy,
            taxonomy_miss=False,
        )

    except Exception as exc:
        logger.error(
            "risk_score_endpoint_error customer_id=%s product_id=%s error=%s",
            request.customer_id,
            request.product_id,
            str(exc),
        )
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Service temporarily unavailable",
                "error": str(exc),
            },
        )
