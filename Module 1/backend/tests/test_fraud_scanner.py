"""
Unit tests for FraudScanner service.

Tests the mock Social Connect fraud scanning logic including category
filtering, threshold enforcement, error handling, and deterministic output.

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8
"""

from datetime import date

import pytest

from app.models.results import FraudScanResult
from app.services.fraud_scanner import ELIGIBLE_CATEGORY, MATCH_THRESHOLD, FraudScanner


@pytest.fixture
def scanner() -> FraudScanner:
    return FraudScanner()


@pytest.fixture
def ownership_window() -> tuple[date, date]:
    return (date(2026, 5, 1), date(2026, 5, 20))


@pytest.fixture
def connected_accounts() -> list[str]:
    return ["instagram_user123", "facebook_user123", "x_user123"]


@pytest.fixture
def product_images() -> list[str]:
    return ["s3://catalog/product_front.jpg", "s3://catalog/product_back.jpg"]


# ---------------------------------------------------------------------------
# Test: Category filtering (Requirement 4.1)
# ---------------------------------------------------------------------------


class TestCategoryFiltering:
    def test_executes_for_clothing_and_footwear(
        self, scanner: FraudScanner, ownership_window, connected_accounts, product_images
    ):
        """Fraud scan should execute when category is 'Clothing & Footwear'."""
        result = scanner.scan(
            customer_id="CUST-001",
            product_images=product_images,
            ownership_window=ownership_window,
            connected_accounts=connected_accounts,
            category="Clothing & Footwear",
        )
        assert result.social_scan_performed is True

    def test_skips_for_electronics(
        self, scanner: FraudScanner, ownership_window, connected_accounts, product_images
    ):
        """Fraud scan should NOT execute for Electronics category."""
        result = scanner.scan(
            customer_id="CUST-001",
            product_images=product_images,
            ownership_window=ownership_window,
            connected_accounts=connected_accounts,
            category="Electronics",
        )
        assert result.social_scan_performed is False
        assert result.fraud_confidence == 0.0
        assert result.evidence_posts == []

    def test_skips_for_food_and_grocery(
        self, scanner: FraudScanner, ownership_window, connected_accounts, product_images
    ):
        """Fraud scan should NOT execute for Food & Grocery category."""
        result = scanner.scan(
            customer_id="CUST-001",
            product_images=product_images,
            ownership_window=ownership_window,
            connected_accounts=connected_accounts,
            category="Food & Grocery",
        )
        assert result.social_scan_performed is False
        assert result.fraud_confidence == 0.0

    def test_skips_for_other_category(
        self, scanner: FraudScanner, ownership_window, connected_accounts, product_images
    ):
        """Fraud scan should NOT execute for 'Other' category."""
        result = scanner.scan(
            customer_id="CUST-001",
            product_images=product_images,
            ownership_window=ownership_window,
            connected_accounts=connected_accounts,
            category="Other",
        )
        assert result.social_scan_performed is False
        assert result.fraud_confidence == 0.0


# ---------------------------------------------------------------------------
# Test: No connected accounts (Requirement 4.7)
# ---------------------------------------------------------------------------


class TestNoConnectedAccounts:
    def test_no_accounts_skips_scan(
        self, scanner: FraudScanner, ownership_window, product_images
    ):
        """With no connected accounts, scan should not execute."""
        result = scanner.scan(
            customer_id="CUST-001",
            product_images=product_images,
            ownership_window=ownership_window,
            connected_accounts=[],
            category="Clothing & Footwear",
        )
        assert result.social_scan_performed is False
        assert result.fraud_confidence == 0.0
        assert result.accounts_scanned == []
        assert result.product_found_in_social is False

    def test_no_accounts_still_has_scan_window(
        self, scanner: FraudScanner, ownership_window, product_images
    ):
        """Even with no accounts, scan window should be populated."""
        result = scanner.scan(
            customer_id="CUST-001",
            product_images=product_images,
            ownership_window=ownership_window,
            connected_accounts=[],
            category="Clothing & Footwear",
        )
        assert result.scan_window == {"from": "2026-05-01", "to": "2026-05-20"}


# ---------------------------------------------------------------------------
# Test: Evidence recording and threshold (Requirements 4.3, 4.4)
# ---------------------------------------------------------------------------


class TestEvidenceThreshold:
    def test_evidence_posts_above_threshold(
        self, scanner: FraudScanner, ownership_window, connected_accounts, product_images
    ):
        """All recorded evidence posts must have match_confidence > 0.70."""
        result = scanner.scan(
            customer_id="CUST-001",
            product_images=product_images,
            ownership_window=ownership_window,
            connected_accounts=connected_accounts,
            category="Clothing & Footwear",
        )
        for post in result.evidence_posts:
            assert post["match_confidence"] > MATCH_THRESHOLD

    def test_evidence_post_structure(
        self, scanner: FraudScanner, ownership_window, connected_accounts, product_images
    ):
        """Evidence posts must contain required fields: platform, post_date, match_confidence, post_type."""
        result = scanner.scan(
            customer_id="CUST-002",
            product_images=product_images,
            ownership_window=ownership_window,
            connected_accounts=connected_accounts,
            category="Clothing & Footwear",
        )
        # Run with enough accounts to likely generate evidence
        if result.evidence_posts:
            for post in result.evidence_posts:
                assert "platform" in post
                assert "post_date" in post
                assert "match_confidence" in post
                assert "post_type" in post
                assert isinstance(post["platform"], str)
                assert isinstance(post["post_date"], str)
                assert isinstance(post["match_confidence"], float)
                assert isinstance(post["post_type"], str)


# ---------------------------------------------------------------------------
# Test: Scan output structure (Requirement 4.5)
# ---------------------------------------------------------------------------


class TestScanOutput:
    def test_returns_fraud_scan_result(
        self, scanner: FraudScanner, ownership_window, connected_accounts, product_images
    ):
        """scan() should return a FraudScanResult dataclass."""
        result = scanner.scan(
            customer_id="CUST-001",
            product_images=product_images,
            ownership_window=ownership_window,
            connected_accounts=connected_accounts,
            category="Clothing & Footwear",
        )
        assert isinstance(result, FraudScanResult)

    def test_accounts_scanned_matches_input(
        self, scanner: FraudScanner, ownership_window, connected_accounts, product_images
    ):
        """accounts_scanned should list all connected accounts when scan is performed."""
        result = scanner.scan(
            customer_id="CUST-001",
            product_images=product_images,
            ownership_window=ownership_window,
            connected_accounts=connected_accounts,
            category="Clothing & Footwear",
        )
        assert result.accounts_scanned == connected_accounts

    def test_scan_window_format(
        self, scanner: FraudScanner, ownership_window, connected_accounts, product_images
    ):
        """scan_window should have 'from' and 'to' ISO-formatted date strings."""
        result = scanner.scan(
            customer_id="CUST-001",
            product_images=product_images,
            ownership_window=ownership_window,
            connected_accounts=connected_accounts,
            category="Clothing & Footwear",
        )
        assert "from" in result.scan_window
        assert "to" in result.scan_window
        assert result.scan_window["from"] == "2026-05-01"
        assert result.scan_window["to"] == "2026-05-20"

    def test_fraud_confidence_in_valid_range(
        self, scanner: FraudScanner, ownership_window, connected_accounts, product_images
    ):
        """fraud_confidence must be between 0.0 and 1.0."""
        result = scanner.scan(
            customer_id="CUST-001",
            product_images=product_images,
            ownership_window=ownership_window,
            connected_accounts=connected_accounts,
            category="Clothing & Footwear",
        )
        assert 0.0 <= result.fraud_confidence <= 1.0


# ---------------------------------------------------------------------------
# Test: Deterministic output (mock reproducibility)
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_same_customer_produces_same_result(
        self, scanner: FraudScanner, ownership_window, connected_accounts, product_images
    ):
        """Same customer_id should produce identical results (deterministic seed)."""
        result1 = scanner.scan(
            customer_id="CUST-REPEAT",
            product_images=product_images,
            ownership_window=ownership_window,
            connected_accounts=connected_accounts,
            category="Clothing & Footwear",
        )
        result2 = scanner.scan(
            customer_id="CUST-REPEAT",
            product_images=product_images,
            ownership_window=ownership_window,
            connected_accounts=connected_accounts,
            category="Clothing & Footwear",
        )
        assert result1.fraud_confidence == result2.fraud_confidence
        assert result1.evidence_posts == result2.evidence_posts
        assert result1.product_found_in_social == result2.product_found_in_social

    def test_different_customers_produce_different_results(
        self, scanner: FraudScanner, ownership_window, connected_accounts, product_images
    ):
        """Different customer_ids should generally produce different results."""
        result1 = scanner.scan(
            customer_id="CUST-AAA",
            product_images=product_images,
            ownership_window=ownership_window,
            connected_accounts=connected_accounts,
            category="Clothing & Footwear",
        )
        result2 = scanner.scan(
            customer_id="CUST-ZZZ",
            product_images=product_images,
            ownership_window=ownership_window,
            connected_accounts=connected_accounts,
            category="Clothing & Footwear",
        )
        # At least one field should differ (extremely unlikely to be identical)
        differs = (
            result1.fraud_confidence != result2.fraud_confidence
            or result1.evidence_posts != result2.evidence_posts
        )
        assert differs


# ---------------------------------------------------------------------------
# Test: Scan window scope (Requirement 4.6)
# ---------------------------------------------------------------------------


class TestScanWindowScope:
    def test_evidence_posts_within_ownership_window(
        self, scanner: FraudScanner, connected_accounts, product_images
    ):
        """All evidence post dates should fall within the ownership window."""
        window = (date(2026, 6, 1), date(2026, 6, 15))
        result = scanner.scan(
            customer_id="CUST-WINDOW",
            product_images=product_images,
            ownership_window=window,
            connected_accounts=connected_accounts,
            category="Clothing & Footwear",
        )
        for post in result.evidence_posts:
            post_date = date.fromisoformat(post["post_date"])
            assert window[0] <= post_date <= window[1]


# ---------------------------------------------------------------------------
# Test: Error handling (Requirement 4.8)
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def test_graceful_error_returns_scan_not_performed(self):
        """If an internal error occurs, return social_scan_performed=False."""

        class BrokenFraudScanner(FraudScanner):
            def _execute_mock_scan(self, *args, **kwargs):
                raise RuntimeError("Simulated Social Connect API failure")

        scanner = BrokenFraudScanner()
        result = scanner.scan(
            customer_id="CUST-ERR",
            product_images=["s3://img.jpg"],
            ownership_window=(date(2026, 5, 1), date(2026, 5, 20)),
            connected_accounts=["instagram_user"],
            category="Clothing & Footwear",
        )
        assert result.social_scan_performed is False
        assert result.fraud_confidence == 0.0
        assert result.evidence_posts == []


# ---------------------------------------------------------------------------
# Test: Product found logic
# ---------------------------------------------------------------------------


class TestProductFoundLogic:
    def test_product_found_when_evidence_exists(
        self, scanner: FraudScanner, ownership_window, product_images
    ):
        """product_found_in_social should be True when evidence_posts is non-empty."""
        # Use many accounts to increase likelihood of finding matches
        accounts = [f"instagram_user{i}" for i in range(10)]
        result = scanner.scan(
            customer_id="CUST-FOUND",
            product_images=product_images,
            ownership_window=ownership_window,
            connected_accounts=accounts,
            category="Clothing & Footwear",
        )
        if result.evidence_posts:
            assert result.product_found_in_social is True
        else:
            assert result.product_found_in_social is False

    def test_no_product_found_means_zero_confidence(
        self, scanner: FraudScanner, ownership_window, product_images
    ):
        """If no evidence posts are found, fraud_confidence should be 0.0."""
        # Use a customer_id that we know produces no evidence (or verify the logic)
        result = scanner.scan(
            customer_id="CUST-CLEAN",
            product_images=product_images,
            ownership_window=ownership_window,
            connected_accounts=["instagram_clean"],
            category="Clothing & Footwear",
        )
        if not result.evidence_posts:
            assert result.fraud_confidence == 0.0
