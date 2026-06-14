"""
ReturnRequest and CatalogMetadata Pydantic models.

These models represent the input data for initiating and processing a return.
"""

from pydantic import BaseModel, Field


class CatalogMetadata(BaseModel):
    """Product catalog metadata provided with a return submission."""

    category: str
    original_price: float = Field(gt=0)
    purchase_date: str  # ISO 8601 date string
    warranty_remaining_months: int = Field(ge=0)


class ReturnRequest(BaseModel):
    """Request payload for initiating a return."""

    order_id: str
    product_id: str
    customer_id: str
