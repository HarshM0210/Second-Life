"""
Unit tests for Disposition Router service.

Tests cover:
- Gate A (economics check)
- Gate B (health score thresholds)
- Food & Grocery category overrides (Requirement 19)
- Safety and Hygiene overrides (Requirement 20)
- Priority ordering of overrides
"""

from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from app.models.results import DispositionResult
from app.services.disposition_router import DispositionRouter


@pytest.fixture
def router():
    return DispositionRouter()


# ─── Helper: default qa_answers ───────────────────────────────────────────────

def base_qa():
    """Minimal Q&A answers with no override triggers."""
    return {
        "return_reason": "Changed my mind / no longer needed",
        "safety_concern": "No safety concerns",
        "liquid_damage": "No — never exposed to liquid or impact",
        "factory_reset": "Yes — fully reset, personal data removed",
        "skin_contact": "No",
    }


def food_qa_sealed_unexpired():
    """Food & Grocery sealed, unexpired, non-wrong-item."""
    future_date = (date.today() + timedelta(days=30)).isoformat()
    return {
        "return_reason": "Quality not as expected",
        "seal_integrity": "Yes — completely sealed, never opened",
        "quantity_remaining": "100% — completely unused",
        "expiry_date": future_date,
        "safety_concern": "No safety concerns",
        "liquid_damage": "No — never exposed to liquid or impact",
    }


# ─── Gate A Tests ─────────────────────────────────────────────────────────────

class TestGateA:
    """Tests for Gate A economics check."""

    @pytest.mark.asyncio
    @patch("app.services.disposition_router.DispositionRouter._get_processing_cost")
    async def test_cost_less_than_value_returns_to_seller(self, mock_cost, router):
        mock_cost.return_value = 50.0
        result = await router.route(
            health_score=85,
            fraud_confidence=0.1,
            category="Electronics",
            qa_answers=base_qa(),
            product_value=100.0,
        )
        assert result.disposition == "return_to_seller"
        assert result.gate_applied == "A"

    @pytest.mark.asyncio
    @patch("app.services.disposition_router.DispositionRouter._get_processing_cost")
    async def test_cost_equal_to_value_proceeds_to_gate_b(self, mock_cost, router):
        mock_cost.return_value = 100.0
        result = await router.route(
            health_score=95,
            fraud_confidence=0.1,
            category="Electronics",
            qa_answers=base_qa(),
            product_value=100.0,
        )
        # cost >= value → Gate B; score 95 → resell
        assert result.disposition == "resell"
        assert result.gate_applied == "B"

    @pytest.mark.asyncio
    @patch("app.services.disposition_router.DispositionRouter._get_processing_cost")
    async def test_cost_greater_than_value_proceeds_to_gate_b(self, mock_cost, router):
        mock_cost.return_value = 150.0
        result = await router.route(
            health_score=45,
            fraud_confidence=0.1,
            category="Electronics",
            qa_answers=base_qa(),
            product_value=100.0,
        )
        # cost >= value → Gate B; score 45 → recycle
        assert result.disposition == "recycle"
        assert result.gate_applied == "B"

    @pytest.mark.asyncio
    @patch("app.services.disposition_router.DispositionRouter._get_processing_cost")
    async def test_missing_category_in_cost_table(self, mock_cost, router):
        mock_cost.return_value = None
        result = await router.route(
            health_score=85,
            fraud_confidence=0.1,
            category="UnknownCategory",
            qa_answers=base_qa(),
            product_value=100.0,
        )
        assert result.disposition == "manual_review"
        assert result.gate_applied == "A"
        assert "category_not_in_cost_table" in result.flags


# ─── Gate B Tests ─────────────────────────────────────────────────────────────

class TestGateB:
    """Tests for Gate B health score thresholds."""

    @pytest.mark.asyncio
    @patch("app.services.disposition_router.DispositionRouter._get_processing_cost")
    async def test_score_above_90_resell(self, mock_cost, router):
        mock_cost.return_value = 200.0  # force Gate B
        result = await router.route(
            health_score=91,
            fraud_confidence=0.1,
            category="Electronics",
            qa_answers=base_qa(),
            product_value=100.0,
        )
        assert result.disposition == "resell"
        assert result.gate_applied == "B"

    @pytest.mark.asyncio
    @patch("app.services.disposition_router.DispositionRouter._get_processing_cost")
    async def test_score_exactly_90_refurbish(self, mock_cost, router):
        mock_cost.return_value = 200.0
        result = await router.route(
            health_score=90,
            fraud_confidence=0.1,
            category="Electronics",
            qa_answers=base_qa(),
            product_value=100.0,
        )
        assert result.disposition == "refurbish"
        assert result.gate_applied == "B"

    @pytest.mark.asyncio
    @patch("app.services.disposition_router.DispositionRouter._get_processing_cost")
    async def test_score_71_refurbish(self, mock_cost, router):
        mock_cost.return_value = 200.0
        result = await router.route(
            health_score=71,
            fraud_confidence=0.1,
            category="Electronics",
            qa_answers=base_qa(),
            product_value=100.0,
        )
        assert result.disposition == "refurbish"
        assert result.gate_applied == "B"

    @pytest.mark.asyncio
    @patch("app.services.disposition_router.DispositionRouter._get_processing_cost")
    async def test_score_exactly_70_donate(self, mock_cost, router):
        mock_cost.return_value = 200.0
        result = await router.route(
            health_score=70,
            fraud_confidence=0.1,
            category="Electronics",
            qa_answers=base_qa(),
            product_value=100.0,
        )
        assert result.disposition == "donate"
        assert result.gate_applied == "B"

    @pytest.mark.asyncio
    @patch("app.services.disposition_router.DispositionRouter._get_processing_cost")
    async def test_score_51_donate(self, mock_cost, router):
        mock_cost.return_value = 200.0
        result = await router.route(
            health_score=51,
            fraud_confidence=0.1,
            category="Electronics",
            qa_answers=base_qa(),
            product_value=100.0,
        )
        assert result.disposition == "donate"
        assert result.gate_applied == "B"

    @pytest.mark.asyncio
    @patch("app.services.disposition_router.DispositionRouter._get_processing_cost")
    async def test_score_exactly_50_recycle(self, mock_cost, router):
        mock_cost.return_value = 200.0
        result = await router.route(
            health_score=50,
            fraud_confidence=0.1,
            category="Electronics",
            qa_answers=base_qa(),
            product_value=100.0,
        )
        assert result.disposition == "recycle"
        assert result.gate_applied == "B"

    @pytest.mark.asyncio
    @patch("app.services.disposition_router.DispositionRouter._get_processing_cost")
    async def test_score_zero_recycle(self, mock_cost, router):
        mock_cost.return_value = 200.0
        result = await router.route(
            health_score=0,
            fraud_confidence=0.1,
            category="Electronics",
            qa_answers=base_qa(),
            product_value=100.0,
        )
        assert result.disposition == "recycle"
        assert result.gate_applied == "B"


# ─── Food & Grocery Override Tests (Requirement 19) ───────────────────────────

class TestFoodGroceryOverrides:
    """Tests for Food & Grocery category-specific overrides."""

    @pytest.mark.asyncio
    @patch("app.services.disposition_router.DispositionRouter._get_processing_cost")
    async def test_seal_broken_recycle(self, mock_cost, router):
        """Req 19.1: Seal broken → recycle regardless of score."""
        mock_cost.return_value = 10.0  # would normally route to return_to_seller
        qa = food_qa_sealed_unexpired()
        qa["seal_integrity"] = "No — seal broken or packaging opened"

        result = await router.route(
            health_score=95,
            fraud_confidence=0.0,
            category="Food & Grocery",
            qa_answers=qa,
            product_value=100.0,
        )
        assert result.disposition == "recycle"
        assert result.gate_applied == "category_override"
        assert "seal_broken" in result.flags

    @pytest.mark.asyncio
    @patch("app.services.disposition_router.DispositionRouter._get_processing_cost")
    async def test_partially_used_recycle(self, mock_cost, router):
        """Req 19.1: Partially used → recycle."""
        mock_cost.return_value = 10.0
        qa = food_qa_sealed_unexpired()
        qa["quantity_remaining"] = "Partially used"

        result = await router.route(
            health_score=95,
            fraud_confidence=0.0,
            category="Food & Grocery",
            qa_answers=qa,
            product_value=100.0,
        )
        assert result.disposition == "recycle"
        assert result.gate_applied == "category_override"
        assert "consumed" in result.flags

    @pytest.mark.asyncio
    @patch("app.services.disposition_router.DispositionRouter._get_processing_cost")
    async def test_mostly_consumed_recycle(self, mock_cost, router):
        """Req 19.1: Mostly consumed → recycle."""
        mock_cost.return_value = 10.0
        qa = food_qa_sealed_unexpired()
        qa["quantity_remaining"] = "Mostly consumed"

        result = await router.route(
            health_score=95,
            fraud_confidence=0.0,
            category="Food & Grocery",
            qa_answers=qa,
            product_value=100.0,
        )
        assert result.disposition == "recycle"
        assert result.gate_applied == "category_override"
        assert "consumed" in result.flags

    @pytest.mark.asyncio
    @patch("app.services.disposition_router.DispositionRouter._get_processing_cost")
    async def test_expired_recycle(self, mock_cost, router):
        """Req 19.2: Expired → recycle regardless of score."""
        mock_cost.return_value = 10.0
        qa = food_qa_sealed_unexpired()
        qa["expiry_date"] = (date.today() - timedelta(days=1)).isoformat()

        result = await router.route(
            health_score=95,
            fraud_confidence=0.0,
            category="Food & Grocery",
            qa_answers=qa,
            product_value=100.0,
        )
        assert result.disposition == "recycle"
        assert result.gate_applied == "category_override"
        assert "expired" in result.flags

    @pytest.mark.asyncio
    @patch("app.services.disposition_router.DispositionRouter._get_processing_cost")
    async def test_sealed_unexpired_wrong_item_return_to_seller(self, mock_cost, router):
        """Req 19.3: Sealed + unexpired + 'Wrong item delivered' → return_to_seller."""
        mock_cost.return_value = 200.0  # would normally go to Gate B
        qa = food_qa_sealed_unexpired()
        qa["return_reason"] = "Wrong item delivered"

        result = await router.route(
            health_score=30,
            fraud_confidence=0.0,
            category="Food & Grocery",
            qa_answers=qa,
            product_value=100.0,
        )
        assert result.disposition == "return_to_seller"
        assert result.gate_applied == "category_override"

    @pytest.mark.asyncio
    @patch("app.services.disposition_router.DispositionRouter._get_processing_cost")
    async def test_sealed_unexpired_other_reason_normal_flow(self, mock_cost, router):
        """Req 19.4: Sealed + unexpired + other reason → normal Gate A/B."""
        mock_cost.return_value = 10.0  # cost < value → return_to_seller via Gate A
        qa = food_qa_sealed_unexpired()
        qa["return_reason"] = "Quality not as expected"

        result = await router.route(
            health_score=85,
            fraud_confidence=0.0,
            category="Food & Grocery",
            qa_answers=qa,
            product_value=100.0,
        )
        assert result.disposition == "return_to_seller"
        assert result.gate_applied == "A"

    @pytest.mark.asyncio
    @patch("app.services.disposition_router.DispositionRouter._get_processing_cost")
    async def test_sealed_unexpired_other_reason_gate_b(self, mock_cost, router):
        """Req 19.4: Sealed + unexpired + other reason → Gate B when cost >= value."""
        mock_cost.return_value = 200.0
        qa = food_qa_sealed_unexpired()
        qa["return_reason"] = "Quality not as expected"

        result = await router.route(
            health_score=85,
            fraud_confidence=0.0,
            category="Food & Grocery",
            qa_answers=qa,
            product_value=100.0,
        )
        assert result.disposition == "refurbish"
        assert result.gate_applied == "B"

    @pytest.mark.asyncio
    @patch("app.services.disposition_router.DispositionRouter._get_processing_cost")
    async def test_seal_broken_and_consumed_recycle(self, mock_cost, router):
        """Both seal broken and consumed → recycle with both flags."""
        mock_cost.return_value = 10.0
        qa = food_qa_sealed_unexpired()
        qa["seal_integrity"] = "No — seal broken or packaging opened"
        qa["quantity_remaining"] = "Partially used"

        result = await router.route(
            health_score=95,
            fraud_confidence=0.0,
            category="Food & Grocery",
            qa_answers=qa,
            product_value=100.0,
        )
        assert result.disposition == "recycle"
        assert "seal_broken" in result.flags
        assert "consumed" in result.flags

    @pytest.mark.asyncio
    @patch("app.services.disposition_router.DispositionRouter._get_processing_cost")
    async def test_expiry_today_not_expired(self, mock_cost, router):
        """Expiry date == today is NOT expired (must be < today)."""
        mock_cost.return_value = 10.0
        qa = food_qa_sealed_unexpired()
        qa["expiry_date"] = date.today().isoformat()
        qa["return_reason"] = "Wrong item delivered"

        result = await router.route(
            health_score=85,
            fraud_confidence=0.0,
            category="Food & Grocery",
            qa_answers=qa,
            product_value=100.0,
        )
        # Not expired → sealed + unexpired + wrong item → return_to_seller
        assert result.disposition == "return_to_seller"
        assert result.gate_applied == "category_override"

    @pytest.mark.asyncio
    @patch("app.services.disposition_router.DispositionRouter._get_processing_cost")
    async def test_empty_expiry_date_not_expired(self, mock_cost, router):
        """Empty expiry date string → not expired."""
        mock_cost.return_value = 10.0
        qa = food_qa_sealed_unexpired()
        qa["expiry_date"] = ""
        qa["return_reason"] = "Wrong item delivered"

        result = await router.route(
            health_score=85,
            fraud_confidence=0.0,
            category="Food & Grocery",
            qa_answers=qa,
            product_value=100.0,
        )
        assert result.disposition == "return_to_seller"
        assert result.gate_applied == "category_override"


# ─── Safety Override Tests (Requirement 20.1) ─────────────────────────────────

class TestSafetyOverrides:
    """Tests for safety concern overrides — highest priority."""

    @pytest.mark.asyncio
    @patch("app.services.disposition_router.DispositionRouter._get_processing_cost")
    async def test_safety_concern_unsafe_manual_review(self, mock_cost, router):
        """Req 20.1: 'Yes — I believe this item is unsafe' → manual_review."""
        mock_cost.return_value = 10.0
        qa = base_qa()
        qa["safety_concern"] = "Yes — I believe this item is unsafe"

        result = await router.route(
            health_score=95,
            fraud_confidence=0.0,
            category="Other",
            qa_answers=qa,
            product_value=100.0,
        )
        assert result.disposition == "manual_review"
        assert result.gate_applied == "safety_hold"
        assert "safety_concern" in result.flags

    @pytest.mark.asyncio
    @patch("app.services.disposition_router.DispositionRouter._get_processing_cost")
    async def test_safety_concern_minor_manual_review(self, mock_cost, router):
        """Req 20.1: 'Minor concern (describe in notes)' → manual_review."""
        mock_cost.return_value = 10.0
        qa = base_qa()
        qa["safety_concern"] = "Minor concern (describe in notes)"

        result = await router.route(
            health_score=95,
            fraud_confidence=0.0,
            category="Other",
            qa_answers=qa,
            product_value=100.0,
        )
        assert result.disposition == "manual_review"
        assert result.gate_applied == "safety_hold"
        assert "safety_concern" in result.flags

    @pytest.mark.asyncio
    @patch("app.services.disposition_router.DispositionRouter._get_processing_cost")
    async def test_significant_liquid_damage_manual_review(self, mock_cost, router):
        """Req 20.1: Significant liquid damage → manual_review."""
        mock_cost.return_value = 10.0
        qa = base_qa()
        qa["liquid_damage"] = "Significant liquid damage (submerged, heavy exposure)"

        result = await router.route(
            health_score=95,
            fraud_confidence=0.0,
            category="Electronics",
            qa_answers=qa,
            product_value=100.0,
        )
        assert result.disposition == "manual_review"
        assert result.gate_applied == "safety_hold"
        assert "liquid_damage" in result.flags

    @pytest.mark.asyncio
    @patch("app.services.disposition_router.DispositionRouter._get_processing_cost")
    async def test_safety_overrides_food_category(self, mock_cost, router):
        """Safety override applies even to Food & Grocery (highest priority)."""
        mock_cost.return_value = 10.0
        qa = food_qa_sealed_unexpired()
        qa["safety_concern"] = "Yes — I believe this item is unsafe"

        result = await router.route(
            health_score=95,
            fraud_confidence=0.0,
            category="Food & Grocery",
            qa_answers=qa,
            product_value=100.0,
        )
        assert result.disposition == "manual_review"
        assert result.gate_applied == "safety_hold"

    @pytest.mark.asyncio
    @patch("app.services.disposition_router.DispositionRouter._get_processing_cost")
    async def test_safety_overrides_electronics(self, mock_cost, router):
        """Safety override applies to Electronics category."""
        mock_cost.return_value = 10.0
        qa = base_qa()
        qa["liquid_damage"] = "Significant liquid damage (submerged, heavy exposure)"

        result = await router.route(
            health_score=95,
            fraud_confidence=0.0,
            category="Electronics",
            qa_answers=qa,
            product_value=100.0,
        )
        assert result.disposition == "manual_review"
        assert result.gate_applied == "safety_hold"

    @pytest.mark.asyncio
    @patch("app.services.disposition_router.DispositionRouter._get_processing_cost")
    async def test_no_safety_concern_proceeds(self, mock_cost, router):
        """No safety concerns → proceeds to next gate."""
        mock_cost.return_value = 10.0
        qa = base_qa()
        qa["safety_concern"] = "No safety concerns"
        qa["liquid_damage"] = "No — never exposed to liquid or impact"

        result = await router.route(
            health_score=85,
            fraud_confidence=0.0,
            category="Other",
            qa_answers=qa,
            product_value=100.0,
        )
        # Should reach Gate A (cost < value → return_to_seller)
        assert result.disposition == "return_to_seller"
        assert result.gate_applied == "A"

    @pytest.mark.asyncio
    @patch("app.services.disposition_router.DispositionRouter._get_processing_cost")
    async def test_both_safety_and_liquid_flags(self, mock_cost, router):
        """Both safety concern and liquid damage → manual_review with both flags."""
        mock_cost.return_value = 10.0
        qa = base_qa()
        qa["safety_concern"] = "Yes — I believe this item is unsafe"
        qa["liquid_damage"] = "Significant liquid damage (submerged, heavy exposure)"

        result = await router.route(
            health_score=95,
            fraud_confidence=0.0,
            category="Electronics",
            qa_answers=qa,
            product_value=100.0,
        )
        assert result.disposition == "manual_review"
        assert result.gate_applied == "safety_hold"
        assert "safety_concern" in result.flags
        assert "liquid_damage" in result.flags


# ─── Electronics Factory Reset Override Tests (Requirement 20.3) ──────────────

class TestElectronicsResetOverride:
    """Tests for Electronics factory reset override."""

    @pytest.mark.asyncio
    @patch("app.services.disposition_router.DispositionRouter._get_processing_cost")
    async def test_unreset_device_manual_review(self, mock_cost, router):
        """Req 20.3: Unreset device → manual_review with factory_reset_required."""
        mock_cost.return_value = 10.0
        qa = base_qa()
        qa["factory_reset"] = "No — personal data still on device"

        result = await router.route(
            health_score=95,
            fraud_confidence=0.0,
            category="Electronics",
            qa_answers=qa,
            product_value=100.0,
        )
        assert result.disposition == "manual_review"
        assert result.gate_applied == "safety_hold"
        assert "factory_reset_required" in result.flags

    @pytest.mark.asyncio
    @patch("app.services.disposition_router.DispositionRouter._get_processing_cost")
    async def test_reset_device_normal_flow(self, mock_cost, router):
        """Reset device → normal flow."""
        mock_cost.return_value = 10.0
        qa = base_qa()
        qa["factory_reset"] = "Yes — fully reset, personal data removed"

        result = await router.route(
            health_score=85,
            fraud_confidence=0.0,
            category="Electronics",
            qa_answers=qa,
            product_value=100.0,
        )
        # Should proceed to Gate A → return_to_seller
        assert result.disposition == "return_to_seller"
        assert result.gate_applied == "A"

    @pytest.mark.asyncio
    @patch("app.services.disposition_router.DispositionRouter._get_processing_cost")
    async def test_not_applicable_normal_flow(self, mock_cost, router):
        """Req 20.4: 'Not applicable' → normal flow (no hold)."""
        mock_cost.return_value = 10.0
        qa = base_qa()
        qa["factory_reset"] = "Not applicable for this product"

        result = await router.route(
            health_score=85,
            fraud_confidence=0.0,
            category="Electronics",
            qa_answers=qa,
            product_value=100.0,
        )
        assert result.disposition == "return_to_seller"
        assert result.gate_applied == "A"

    @pytest.mark.asyncio
    @patch("app.services.disposition_router.DispositionRouter._get_processing_cost")
    async def test_unreset_not_applied_to_other_category(self, mock_cost, router):
        """Factory reset override only applies to Electronics."""
        mock_cost.return_value = 10.0
        qa = base_qa()
        qa["factory_reset"] = "No — personal data still on device"

        result = await router.route(
            health_score=85,
            fraud_confidence=0.0,
            category="Other",
            qa_answers=qa,
            product_value=100.0,
        )
        # Should NOT trigger factory reset hold for Other category
        assert result.disposition == "return_to_seller"
        assert result.gate_applied == "A"


# ─── Hygiene Override Tests (Requirement 20.2) ────────────────────────────────

class TestHygieneOverrides:
    """Tests for hygiene overrides — Other category + skin contact."""

    @pytest.mark.asyncio
    @patch("app.services.disposition_router.DispositionRouter._get_processing_cost")
    async def test_skin_contact_good_condition_donate(self, mock_cost, router):
        """Req 20.2: Skin contact + health_score > 50 → donate."""
        mock_cost.return_value = 10.0
        qa = base_qa()
        qa["skin_contact"] = "Yes — and it HAS been used on skin / body"

        result = await router.route(
            health_score=75,
            fraud_confidence=0.0,
            category="Other",
            qa_answers=qa,
            product_value=100.0,
        )
        assert result.disposition == "donate"
        assert result.gate_applied == "category_override"
        assert "hygiene_skin_contact" in result.flags

    @pytest.mark.asyncio
    @patch("app.services.disposition_router.DispositionRouter._get_processing_cost")
    async def test_skin_contact_poor_condition_recycle(self, mock_cost, router):
        """Req 20.2: Skin contact + health_score <= 50 → recycle."""
        mock_cost.return_value = 10.0
        qa = base_qa()
        qa["skin_contact"] = "Yes — and it HAS been used on skin / body"

        result = await router.route(
            health_score=40,
            fraud_confidence=0.0,
            category="Other",
            qa_answers=qa,
            product_value=100.0,
        )
        assert result.disposition == "recycle"
        assert result.gate_applied == "category_override"
        assert "hygiene_skin_contact" in result.flags

    @pytest.mark.asyncio
    @patch("app.services.disposition_router.DispositionRouter._get_processing_cost")
    async def test_skin_contact_exactly_50_recycle(self, mock_cost, router):
        """Boundary: health_score == 50 → poor condition → recycle."""
        mock_cost.return_value = 10.0
        qa = base_qa()
        qa["skin_contact"] = "Yes — and it HAS been used on skin / body"

        result = await router.route(
            health_score=50,
            fraud_confidence=0.0,
            category="Other",
            qa_answers=qa,
            product_value=100.0,
        )
        assert result.disposition == "recycle"
        assert result.gate_applied == "category_override"

    @pytest.mark.asyncio
    @patch("app.services.disposition_router.DispositionRouter._get_processing_cost")
    async def test_skin_contact_exactly_51_donate(self, mock_cost, router):
        """Boundary: health_score == 51 → good condition → donate."""
        mock_cost.return_value = 10.0
        qa = base_qa()
        qa["skin_contact"] = "Yes — and it HAS been used on skin / body"

        result = await router.route(
            health_score=51,
            fraud_confidence=0.0,
            category="Other",
            qa_answers=qa,
            product_value=100.0,
        )
        assert result.disposition == "donate"
        assert result.gate_applied == "category_override"

    @pytest.mark.asyncio
    @patch("app.services.disposition_router.DispositionRouter._get_processing_cost")
    async def test_no_skin_contact_normal_flow(self, mock_cost, router):
        """No skin contact → normal flow."""
        mock_cost.return_value = 10.0
        qa = base_qa()
        qa["skin_contact"] = "No"

        result = await router.route(
            health_score=85,
            fraud_confidence=0.0,
            category="Other",
            qa_answers=qa,
            product_value=100.0,
        )
        assert result.disposition == "return_to_seller"
        assert result.gate_applied == "A"

    @pytest.mark.asyncio
    @patch("app.services.disposition_router.DispositionRouter._get_processing_cost")
    async def test_skin_not_used_normal_flow(self, mock_cost, router):
        """Skin contact item but NOT used on skin → normal flow."""
        mock_cost.return_value = 10.0
        qa = base_qa()
        qa["skin_contact"] = "Yes — and it has NOT been used on skin"

        result = await router.route(
            health_score=85,
            fraud_confidence=0.0,
            category="Other",
            qa_answers=qa,
            product_value=100.0,
        )
        assert result.disposition == "return_to_seller"
        assert result.gate_applied == "A"

    @pytest.mark.asyncio
    @patch("app.services.disposition_router.DispositionRouter._get_processing_cost")
    async def test_skin_contact_not_applied_to_electronics(self, mock_cost, router):
        """Hygiene skin contact override only applies to Other category."""
        mock_cost.return_value = 10.0
        qa = base_qa()
        qa["skin_contact"] = "Yes — and it HAS been used on skin / body"

        result = await router.route(
            health_score=75,
            fraud_confidence=0.0,
            category="Electronics",
            qa_answers=qa,
            product_value=100.0,
        )
        # Should NOT trigger hygiene override for Electronics
        assert result.disposition == "return_to_seller"
        assert result.gate_applied == "A"


# ─── Priority Ordering Tests ─────────────────────────────────────────────────

class TestPriorityOrdering:
    """Tests that the override priority is correct."""

    @pytest.mark.asyncio
    @patch("app.services.disposition_router.DispositionRouter._get_processing_cost")
    async def test_safety_trumps_food_override(self, mock_cost, router):
        """Safety override (priority 1) overrides Food & Grocery override (priority 2)."""
        mock_cost.return_value = 10.0
        qa = food_qa_sealed_unexpired()
        qa["seal_integrity"] = "No — seal broken or packaging opened"
        qa["safety_concern"] = "Yes — I believe this item is unsafe"

        result = await router.route(
            health_score=95,
            fraud_confidence=0.0,
            category="Food & Grocery",
            qa_answers=qa,
            product_value=100.0,
        )
        # Safety override wins over food override
        assert result.disposition == "manual_review"
        assert result.gate_applied == "safety_hold"

    @pytest.mark.asyncio
    @patch("app.services.disposition_router.DispositionRouter._get_processing_cost")
    async def test_safety_trumps_electronics_reset(self, mock_cost, router):
        """Safety override (priority 1) overrides electronics reset (priority 3)."""
        mock_cost.return_value = 10.0
        qa = base_qa()
        qa["factory_reset"] = "No — personal data still on device"
        qa["liquid_damage"] = "Significant liquid damage (submerged, heavy exposure)"

        result = await router.route(
            health_score=95,
            fraud_confidence=0.0,
            category="Electronics",
            qa_answers=qa,
            product_value=100.0,
        )
        # Safety override wins
        assert result.disposition == "manual_review"
        assert result.gate_applied == "safety_hold"
        assert "liquid_damage" in result.flags

    @pytest.mark.asyncio
    @patch("app.services.disposition_router.DispositionRouter._get_processing_cost")
    async def test_safety_trumps_hygiene(self, mock_cost, router):
        """Safety override (priority 1) overrides hygiene override (priority 4)."""
        mock_cost.return_value = 10.0
        qa = base_qa()
        qa["skin_contact"] = "Yes — and it HAS been used on skin / body"
        qa["safety_concern"] = "Minor concern (describe in notes)"

        result = await router.route(
            health_score=75,
            fraud_confidence=0.0,
            category="Other",
            qa_answers=qa,
            product_value=100.0,
        )
        # Safety override wins over hygiene override
        assert result.disposition == "manual_review"
        assert result.gate_applied == "safety_hold"

    @pytest.mark.asyncio
    @patch("app.services.disposition_router.DispositionRouter._get_processing_cost")
    async def test_food_override_trumps_gate_a(self, mock_cost, router):
        """Food override (priority 2) overrides Gate A (priority 5)."""
        mock_cost.return_value = 10.0  # cost < value → would be return_to_seller
        qa = food_qa_sealed_unexpired()
        qa["seal_integrity"] = "No — seal broken or packaging opened"

        result = await router.route(
            health_score=95,
            fraud_confidence=0.0,
            category="Food & Grocery",
            qa_answers=qa,
            product_value=100.0,
        )
        # Food override wins over Gate A
        assert result.disposition == "recycle"
        assert result.gate_applied == "category_override"

    @pytest.mark.asyncio
    @patch("app.services.disposition_router.DispositionRouter._get_processing_cost")
    async def test_electronics_reset_trumps_gate_a(self, mock_cost, router):
        """Electronics reset (priority 3) overrides Gate A (priority 5)."""
        mock_cost.return_value = 10.0  # cost < value → would be return_to_seller
        qa = base_qa()
        qa["factory_reset"] = "No — personal data still on device"

        result = await router.route(
            health_score=95,
            fraud_confidence=0.0,
            category="Electronics",
            qa_answers=qa,
            product_value=100.0,
        )
        # Factory reset override wins over Gate A
        assert result.disposition == "manual_review"
        assert result.gate_applied == "safety_hold"
        assert "factory_reset_required" in result.flags

    @pytest.mark.asyncio
    @patch("app.services.disposition_router.DispositionRouter._get_processing_cost")
    async def test_hygiene_trumps_gate_a(self, mock_cost, router):
        """Hygiene override (priority 4) overrides Gate A (priority 5)."""
        mock_cost.return_value = 10.0  # cost < value → would be return_to_seller
        qa = base_qa()
        qa["skin_contact"] = "Yes — and it HAS been used on skin / body"

        result = await router.route(
            health_score=75,
            fraud_confidence=0.0,
            category="Other",
            qa_answers=qa,
            product_value=100.0,
        )
        # Hygiene override wins over Gate A
        assert result.disposition == "donate"
        assert result.gate_applied == "category_override"
