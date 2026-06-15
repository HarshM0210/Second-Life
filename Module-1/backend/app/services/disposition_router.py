"""
Disposition Router service.

Applies the following priority chain to determine item disposition:
1. Safety overrides (highest priority) — safety concern → manual_review
2. Food & Grocery overrides — seal broken/expired/consumed → recycle
3. Electronics factory reset override — unreset → manual_review
4. Hygiene overrides for Other category — skin contact → donate or recycle
5. Gate A (economics) — cost < value → return_to_seller
6. Gate B (health score thresholds) — score-based routing
"""

from datetime import date, datetime

import aiosqlite

from app.config.database import DATABASE_PATH
from app.models.results import DispositionResult


class DispositionRouter:
    """Routes items to their highest-value disposition using a multi-gate pipeline."""

    async def route(
        self,
        health_score: int | None,
        fraud_confidence: float,
        category: str,
        qa_answers: dict[str, str],
        product_value: float,
    ) -> DispositionResult:
        """
        Apply disposition routing gates in priority order.

        Priority:
        1. Safety overrides (any category) — highest priority
        2. Food & Grocery category overrides
        3. Electronics factory reset override
        4. Hygiene overrides (Other category)
        5. Gate A: Economics check
        6. Gate B: Health score thresholds

        Args:
            health_score: The computed health score (0–100).
            fraud_confidence: Aggregated fraud confidence (0.0–1.0).
            category: The product category string.
            qa_answers: Structured Q&A answers dict.
            product_value: The original catalog price of the product.

        Returns:
            DispositionResult with disposition, gate_applied, and flags.
        """
        # 1. Safety overrides — highest priority
        safety_result = self._apply_safety_override(qa_answers, category)
        if safety_result is not None:
            return safety_result

        # 2. Food & Grocery overrides
        if category == "Food & Grocery":
            food_result = self._apply_food_grocery_override(qa_answers)
            if food_result is not None:
                return food_result

        # 3. Electronics factory reset override
        if category == "Electronics":
            electronics_result = self._apply_electronics_reset_override(qa_answers)
            if electronics_result is not None:
                return electronics_result

        # 4. Hygiene overrides (Other category)
        if category == "Other":
            hygiene_result = self._apply_hygiene_override(qa_answers, health_score)
            if hygiene_result is not None:
                return hygiene_result

        # 5. Gate A: Economics check
        gate_a_result = await self._apply_gate_a(category, product_value)
        if gate_a_result is not None:
            return gate_a_result

        # 6. Gate B: Health score thresholds
        return self._apply_gate_b(health_score)

    def _apply_safety_override(
        self, qa_answers: dict[str, str], category: str
    ) -> DispositionResult | None:
        """
        Safety override — any safety concern bypasses all gates.

        Triggers:
        - safety_concern: "Yes — I believe this item is unsafe" or
          "Minor concern (describe in notes)"
        - liquid_damage: "Significant liquid damage (submerged, heavy exposure)"

        Returns DispositionResult with "manual_review" or None to continue.
        """
        safety_concern = qa_answers.get("safety_concern", "")
        liquid_damage = qa_answers.get("liquid_damage", "")

        has_safety_concern = safety_concern in (
            "Yes — I believe this item is unsafe",
            "Minor concern (describe in notes)",
        )

        has_significant_liquid_damage = (
            liquid_damage == "Significant liquid damage (submerged, heavy exposure)"
        )

        if has_safety_concern or has_significant_liquid_damage:
            flags = []
            if has_safety_concern:
                flags.append("safety_concern")
            if has_significant_liquid_damage:
                flags.append("liquid_damage")
            return DispositionResult(
                disposition="manual_review",
                gate_applied="safety_hold",
                flags=flags,
            )

        return None

    def _apply_food_grocery_override(
        self, qa_answers: dict[str, str]
    ) -> DispositionResult | None:
        """
        Food & Grocery category-specific overrides.

        Rules:
        - Seal broken OR partially/mostly consumed → "recycle"
        - Expired → "recycle"
        - Sealed + unexpired + "Wrong item delivered" → "return_to_seller"
        - Sealed + unexpired + other reason → None (proceed to normal gates)
        """
        seal_integrity = qa_answers.get("seal_integrity", "")
        quantity_remaining = qa_answers.get("quantity_remaining", "")
        expiry_date_str = qa_answers.get("expiry_date", "")
        return_reason = qa_answers.get("return_reason", "")

        # Check if seal is broken
        seal_broken = seal_integrity == "No — seal broken or packaging opened"

        # Check if partially/mostly consumed
        consumed = quantity_remaining in ("Partially used", "Mostly consumed")

        # Check if expired
        expired = self._is_expired(expiry_date_str)

        # Seal broken OR consumed → recycle
        if seal_broken or consumed:
            flags = []
            if seal_broken:
                flags.append("seal_broken")
            if consumed:
                flags.append("consumed")
            return DispositionResult(
                disposition="recycle",
                gate_applied="category_override",
                flags=flags,
            )

        # Expired → recycle
        if expired:
            return DispositionResult(
                disposition="recycle",
                gate_applied="category_override",
                flags=["expired"],
            )

        # Sealed + unexpired + "Wrong item delivered" → return_to_seller
        sealed = seal_integrity == "Yes — completely sealed, never opened"
        if sealed and not expired and return_reason == "Wrong item delivered":
            return DispositionResult(
                disposition="return_to_seller",
                gate_applied="category_override",
                flags=[],
            )

        # Sealed + unexpired + other reason → proceed to normal gate flow
        return None

    def _apply_electronics_reset_override(
        self, qa_answers: dict[str, str]
    ) -> DispositionResult | None:
        """
        Electronics factory reset override.

        If factory_reset answer is "No — personal data still on device",
        route to manual_review with factory_reset_required flag.

        If "Not applicable for this product", do not apply the hold.
        """
        factory_reset = qa_answers.get("factory_reset", "")

        if factory_reset == "No — personal data still on device":
            return DispositionResult(
                disposition="manual_review",
                gate_applied="safety_hold",
                flags=["factory_reset_required"],
            )

        return None

    def _apply_hygiene_override(
        self, qa_answers: dict[str, str], health_score: int | None
    ) -> DispositionResult | None:
        """
        Hygiene override for Other category.

        If skin_contact is "Yes — and it HAS been used on skin / body":
        - health_score > 50 (good condition) → "donate"
        - health_score <= 50 (poor condition) → "recycle"
        """
        skin_contact = qa_answers.get("skin_contact", "")

        if skin_contact == "Yes — and it HAS been used on skin / body":
            if health_score is not None and health_score > 50:
                return DispositionResult(
                    disposition="donate",
                    gate_applied="category_override",
                    flags=["hygiene_skin_contact"],
                )
            else:
                return DispositionResult(
                    disposition="recycle",
                    gate_applied="category_override",
                    flags=["hygiene_skin_contact"],
                )

        return None

    async def _apply_gate_a(
        self, category: str, product_value: float
    ) -> DispositionResult | None:
        """
        Gate A: Economics check.

        Compares the total processing cost for the category against the product value.
        - If cost < value → "return_to_seller"
        - If cost >= value → None (proceed to Gate B)
        - If category not in cost table → "manual_review"
        """
        total_processing_cost = await self._get_processing_cost(category)

        if total_processing_cost is None:
            return DispositionResult(
                disposition="manual_review",
                gate_applied="A",
                flags=["category_not_in_cost_table"],
            )

        if total_processing_cost < product_value:
            return DispositionResult(
                disposition="return_to_seller",
                gate_applied="A",
                flags=[],
            )

        # cost >= value → proceed to Gate B
        return None

    def _apply_gate_b(self, health_score: int | None) -> DispositionResult:
        """
        Gate B: Health score thresholds.

        Maps health_score to disposition:
        - > 90 → "resell"
        - > 70 and <= 90 → "refurbish"
        - > 50 and <= 70 → "donate"
        - <= 50 → "recycle"
        - None (unavailable) → "recycle" with health_score_unavailable flag
        """
        if health_score is None:
            return DispositionResult(
                disposition="recycle",
                gate_applied="B",
                flags=["health_score_unavailable"],
            )

        if health_score > 90:
            disposition = "resell"
        elif health_score > 70:
            disposition = "refurbish"
        elif health_score > 50:
            disposition = "donate"
        else:
            disposition = "recycle"

        return DispositionResult(
            disposition=disposition,
            gate_applied="B",
            flags=[],
        )

    def _is_expired(self, expiry_date_str: str) -> bool:
        """
        Determine if an item is expired based on the expiry date string.

        The expiry date is compared to today's date.
        If expiry_date < today → expired.

        Handles ISO format dates (YYYY-MM-DD). Returns False if the
        date string is empty or cannot be parsed.
        """
        if not expiry_date_str:
            return False

        try:
            expiry_date = datetime.strptime(expiry_date_str, "%Y-%m-%d").date()
            return expiry_date < date.today()
        except (ValueError, TypeError):
            return False

    async def _get_processing_cost(self, category: str) -> float | None:
        """
        Look up the total processing cost for a category from the cost_lookup table.

        Returns the total_processing_cost if found, or None if category is not in table.
        """
        async with aiosqlite.connect(DATABASE_PATH) as db:
            cursor = await db.execute(
                "SELECT total_processing_cost FROM cost_lookup WHERE category = ?",
                (category,),
            )
            row = await cursor.fetchone()
            if row is not None:
                return row[0]
            return None
