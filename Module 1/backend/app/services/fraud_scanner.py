"""
Fraud Scanner service (Social Connect mock).

Scans connected public social profiles for visual matches of the returned
product within the ownership window. Only executes for Clothing & Footwear
category; skips for all others.

This is a MOCK implementation for the hackathon demo — it simulates the
Social Connect API using deterministic randomness seeded by customer_id.

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8
"""

import hashlib
import logging
import random
from datetime import date

from app.models.results import FraudScanResult

logger = logging.getLogger(__name__)

# Match threshold: only record evidence posts with confidence above this (Req 4.3, 4.4)
MATCH_THRESHOLD: float = 0.70

# Category that triggers the fraud scan (Req 4.1)
ELIGIBLE_CATEGORY: str = "Clothing & Footwear"

# Simulated platforms for the mock
_PLATFORMS: list[str] = ["instagram", "facebook", "x"]

# Simulated post types for the mock
_POST_TYPES: list[str] = ["photo", "story", "reel", "status"]


class FraudScanner:
    """Scans connected social profiles for visual matches of returned products.

    Only executes for Clothing & Footwear. Uses a deterministic mock of the
    Social Connect API for reproducible demo results.
    """

    def scan(
        self,
        customer_id: str,
        product_images: list[str],
        ownership_window: tuple[date, date],
        connected_accounts: list[str],
        category: str = ELIGIBLE_CATEGORY,
    ) -> FraudScanResult:
        """Perform social connect fraud scan.

        Args:
            customer_id: Unique customer identifier.
            product_images: Catalog reference image URIs for visual matching.
            ownership_window: (purchase_date, return_date) tuple scoping the scan.
            connected_accounts: List of connected social platform identifiers.
            category: Product category — scan only executes for Clothing & Footwear.

        Returns:
            FraudScanResult with scan outcome, evidence posts, and confidence.
        """
        # Requirement 4.1: Only execute for Clothing & Footwear
        if category != ELIGIBLE_CATEGORY:
            logger.info(
                "Fraud scan skipped: category '%s' is not '%s'",
                category,
                ELIGIBLE_CATEGORY,
            )
            return FraudScanResult(
                social_scan_performed=False,
                accounts_scanned=[],
                product_found_in_social=False,
                fraud_confidence=0.0,
                evidence_posts=[],
                scan_window={},
            )

        # Requirement 4.7: No connected accounts — no penalty
        if not connected_accounts:
            logger.info(
                "Fraud scan skipped: customer '%s' has no connected accounts",
                customer_id,
            )
            return FraudScanResult(
                social_scan_performed=False,
                accounts_scanned=[],
                product_found_in_social=False,
                fraud_confidence=0.0,
                evidence_posts=[],
                scan_window=self._format_scan_window(ownership_window),
            )

        # Execute the mock scan
        try:
            return self._execute_mock_scan(
                customer_id=customer_id,
                product_images=product_images,
                ownership_window=ownership_window,
                connected_accounts=connected_accounts,
            )
        except Exception as e:
            # Requirement 4.8: Handle API errors gracefully
            logger.error(
                "Fraud scan error for customer '%s': %s",
                customer_id,
                str(e),
            )
            return FraudScanResult(
                social_scan_performed=False,
                accounts_scanned=[],
                product_found_in_social=False,
                fraud_confidence=0.0,
                evidence_posts=[],
                scan_window=self._format_scan_window(ownership_window),
            )

    def _execute_mock_scan(
        self,
        customer_id: str,
        product_images: list[str],
        ownership_window: tuple[date, date],
        connected_accounts: list[str],
    ) -> FraudScanResult:
        """Mock Social Connect API — simulate scanning connected profiles.

        Uses a deterministic seed based on customer_id for reproducibility.
        Generates simulated posts within the ownership window and computes
        visual match confidence scores.
        """
        # Deterministic seed from customer_id for reproducible results
        seed = int(hashlib.sha256(customer_id.encode()).hexdigest(), 16) % (2**32)
        rng = random.Random(seed)

        scan_start, scan_end = ownership_window
        window_days = (scan_end - scan_start).days
        if window_days <= 0:
            window_days = 1

        # Simulate scanning each connected account (Req 4.2, 4.6)
        evidence_posts: list[dict] = []

        for account in connected_accounts:
            # Determine platform from account string or randomly assign
            platform = self._extract_platform(account, rng)

            # Simulate 1-4 posts per account within the ownership window
            num_posts = rng.randint(1, 4)

            for _ in range(num_posts):
                # Generate a random post date within the ownership window (Req 4.6)
                days_offset = rng.randint(0, window_days)
                post_date = scan_start + __import__("datetime").timedelta(days=days_offset)

                # Simulate visual match confidence (Req 4.3)
                match_confidence = round(rng.uniform(0.3, 0.95), 2)

                # Only record evidence if above threshold (Req 4.4)
                if match_confidence > MATCH_THRESHOLD:
                    post_type = rng.choice(_POST_TYPES)
                    evidence_posts.append({
                        "platform": platform,
                        "post_date": post_date.isoformat(),
                        "match_confidence": match_confidence,
                        "post_type": post_type,
                    })

        # Determine if product was found in social media
        product_found = len(evidence_posts) > 0

        # Compute fraud confidence from evidence
        fraud_confidence = self._compute_fraud_confidence(evidence_posts, rng)

        return FraudScanResult(
            social_scan_performed=True,
            accounts_scanned=connected_accounts,
            product_found_in_social=product_found,
            fraud_confidence=fraud_confidence,
            evidence_posts=evidence_posts,
            scan_window=self._format_scan_window(ownership_window),
        )

    def _compute_fraud_confidence(
        self, evidence_posts: list[dict], rng: random.Random
    ) -> float:
        """Compute fraud confidence score from evidence posts.

        If product found in social, confidence is derived from the average
        and max match confidence of the evidence. If not found, returns 0.0.
        """
        if not evidence_posts:
            return 0.0

        confidences = [post["match_confidence"] for post in evidence_posts]
        max_conf = max(confidences)
        avg_conf = sum(confidences) / len(confidences)

        # Weighted combination: 60% max + 40% average
        raw_confidence = 0.6 * max_conf + 0.4 * avg_conf

        # Clamp to [0.0, 1.0]
        fraud_confidence = max(0.0, min(1.0, round(raw_confidence, 2)))
        return fraud_confidence

    def _extract_platform(self, account: str, rng: random.Random) -> str:
        """Extract platform name from account identifier, or assign randomly."""
        account_lower = account.lower()
        for platform in _PLATFORMS:
            if platform in account_lower:
                return platform
        # Fallback: assign a random platform
        return rng.choice(_PLATFORMS)

    def _format_scan_window(self, ownership_window: tuple[date, date]) -> dict[str, str]:
        """Format ownership window as a JSON-friendly dict."""
        return {
            "from": ownership_window[0].isoformat(),
            "to": ownership_window[1].isoformat(),
        }
