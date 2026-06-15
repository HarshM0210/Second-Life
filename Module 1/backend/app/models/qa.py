"""
Q&A-related Pydantic models.

Models for structured question sets, supplementary inputs, and validation results.
"""

from typing import Literal

from pydantic import BaseModel, Field


class SupplementaryInput(BaseModel):
    """Additional input field displayed alongside a question option."""

    type: Literal["text_field", "date_picker"]
    max_length: int | None = None  # 200 for text fields


class Question(BaseModel):
    """A single structured question in a category-specific Q&A set."""

    id: str
    text: str
    options: list[str]
    supplementary_input: SupplementaryInput | None = None
    conditional_display: str | None = None  # e.g., "footwear_only"


class ValidationResult(BaseModel):
    """Result of validating Q&A answer completeness."""

    is_valid: bool
    missing_question_ids: list[str] = Field(default_factory=list)
