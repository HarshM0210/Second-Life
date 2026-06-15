"""
return_prevention/api/routes_fit.py

GET /api/v1/fit-profile/{customer_id}

Returns the customer's fit profile grouped by brand.
Returns HTTP 200 with {} when no rows exist.

Requirements: 2.9, 2.10
"""

from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from return_prevention.db.database import get_db
from return_prevention.db.repositories import FitProfileRepository
from return_prevention.schemas.fit import FitProfileEntry, FitProfileResponse

router = APIRouter(prefix="/api/v1")


@router.get("/fit-profile/{customer_id}", response_model=FitProfileResponse)
def get_fit_profile(
    customer_id: str,
    db: Session = Depends(get_db),
) -> dict[str, list[FitProfileEntry]]:
    """
    Retrieve the fit profile for a customer, grouped by brand.

    Returns an empty dict ({}) with HTTP 200 when no rows exist.
    """
    rows = FitProfileRepository.get_by_customer(db, customer_id)

    if not rows:
        return {}

    grouped: dict[str, list[FitProfileEntry]] = defaultdict(list)
    for row in rows:
        entry = FitProfileEntry(
            order_id=row.order_id,
            purchased_size=row.purchased_size,
            status=row.status,
            return_reason=row.return_reason,
        )
        grouped[row.brand].append(entry)

    return dict(grouped)
