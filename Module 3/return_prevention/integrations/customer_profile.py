"""
return_prevention/integrations/customer_profile.py

Read-only HTTP client for the shared Customer_Profile store (Module 2).
Uses httpx async with a 500 ms timeout. On timeout or connection error,
logs a structured warning and returns None so the FeatureAssembler can
fall back to category-level baselines.

Requirements: 9.1, 9.2, 9.3
"""

from __future__ import annotations

import logging

import httpx

from return_prevention.config import settings

logger = logging.getLogger(__name__)


class CustomerProfileClient:
    """Async HTTP client for the shared Customer_Profile store."""

    def __init__(self, base_url: str | None = None, timeout: float = 0.5) -> None:
        self._base_url = (base_url or settings.CUSTOMER_PROFILE_BASE_URL).rstrip("/")
        self._timeout = httpx.Timeout(timeout)

    async def get(self, customer_id: str) -> dict | None:
        """Fetch customer profile including order_history.

        Returns the parsed JSON response dict on success, or None when
        the upstream service is unreachable or times out.
        """
        url = f"{self._base_url}/api/v2/customer-profile/{customer_id}"

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
                return data
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            logger.warning(
                "customer_profile_unavailable customer_id=%s reason=%s",
                customer_id,
                str(exc),
            )
            return None
