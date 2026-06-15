"""
return_prevention/schemas/fit.py

Pydantic schemas for the Fit Profile endpoint (GET /api/v1/fit-profile/{customer_id}).

Requirements: 2.9
"""

from __future__ import annotations

from pydantic import BaseModel


class FitProfileEntry(BaseModel):
    """A single fit-profile row for a customer–brand pair."""

    order_id: str
    purchased_size: str
    status: str
    return_reason: str | None = None


# The response is a mapping of brand name → list of fit profile entries.
# Using a type alias (RootModel not needed here — the route handler will
# return a plain dict that FastAPI serialises automatically).
FitProfileResponse = dict[str, list[FitProfileEntry]]
