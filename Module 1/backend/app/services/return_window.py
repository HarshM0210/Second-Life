"""
Return Window Validator service.

Determines if a return is within the allowed window for its product category.
Loads configuration from SQLite return_windows table.
"""

from datetime import date, timedelta

import aiosqlite

from app.config.database import DATABASE_PATH
from app.models.results import ReturnWindowResult
from app.services.exceptions import ServiceError

DEFAULT_WINDOW_DAYS = 30


class ReturnWindowValidator:
    """Validates whether a return is within the configured return window."""

    async def validate(self, delivery_date: date, category: str) -> ReturnWindowResult:
        """
        Check if a return is eligible based on the delivery date and category window.

        Args:
            delivery_date: The original delivery date of the order.
            category: The product category (e.g., "Electronics", "Food & Grocery").

        Returns:
            ReturnWindowResult with eligibility status.

        Raises:
            ServiceError: If delivery_date is None or config cannot be retrieved.
        """
        if delivery_date is None:
            raise ServiceError(
                message="Return eligibility could not be verified. Please retry.",
                service="ReturnWindowValidator",
            )

        window_days = await self._get_window_days(category)

        today = date.today()
        days_elapsed = (today - delivery_date).days
        expiry_date = delivery_date + timedelta(days=window_days)
        eligible = days_elapsed <= window_days

        message = None
        if not eligible:
            message = (
                f"Return window expired on {expiry_date.isoformat()}. "
                f"Returns must be initiated within {window_days} days of delivery."
            )

        return ReturnWindowResult(
            eligible=eligible,
            window_days=window_days,
            days_elapsed=days_elapsed,
            expiry_date=expiry_date,
            message=message,
        )

    async def _get_window_days(self, category: str) -> int:
        """Load the return window for a category from SQLite.

        Falls back to DEFAULT_WINDOW_DAYS (30) if no category-specific config exists.

        Raises:
            ServiceError: If the database cannot be read.
        """
        try:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                cursor = await db.execute(
                    "SELECT window_days FROM return_windows WHERE category = ?",
                    (category,),
                )
                row = await cursor.fetchone()
                if row is not None:
                    return row[0]
                return DEFAULT_WINDOW_DAYS
        except Exception as exc:
            raise ServiceError(
                message="Return eligibility could not be verified. Please retry.",
                service="ReturnWindowValidator",
            ) from exc
