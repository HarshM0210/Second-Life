"""
return_prevention/integrations/green_coin.py

Async event emitter for purchase_avoidance events to the Green_Coin_Service.

- POSTs to GREEN_COIN_BASE_URL + /api/v4/purchase-avoidance
- On failure: logs a warning, retries once after 60 seconds
- On second failure: appends the event as JSONL to purchase_avoidance_retry.log

Requirements: 8.3, 8.4
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import httpx

from return_prevention.config import settings
from return_prevention.schemas.events import PurchaseAvoidanceEvent

logger = logging.getLogger(__name__)

_RETRY_LOG_PATH = Path("purchase_avoidance_retry.log")
_RETRY_DELAY_SECONDS = 60


class GreenCoinEmitter:
    """Emits purchase_avoidance events to the Green_Coin_Service."""

    def __init__(self) -> None:
        self._url = settings.GREEN_COIN_BASE_URL.rstrip("/") + "/api/v4/purchase-avoidance"

    async def emit(self, event: PurchaseAvoidanceEvent) -> None:
        """
        POST the event to Green_Coin_Service.

        On first failure: log a warning and retry after 60 seconds.
        On second failure: append the event as JSONL to the retry log.
        """
        payload = event.model_dump(mode="json")

        # First attempt
        success = await self._post(payload, attempt=1)
        if success:
            return

        # Wait and retry once
        logger.warning(
            "green_coin_emit_failed attempt=1 customer_id=%s product_id=%s "
            "reason='scheduling retry after %d seconds'",
            event.customer_id,
            event.product_id,
            _RETRY_DELAY_SECONDS,
        )
        await asyncio.sleep(_RETRY_DELAY_SECONDS)

        success = await self._post(payload, attempt=2)
        if success:
            return

        # Both attempts failed — write to retry log
        logger.warning(
            "green_coin_emit_failed attempt=2 customer_id=%s product_id=%s "
            "reason='writing to retry log'",
            event.customer_id,
            event.product_id,
        )
        self._write_to_retry_log(payload)

    async def _post(self, payload: dict, attempt: int) -> bool:
        """Attempt a single POST. Returns True on success, False on failure."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(self._url, json=payload, timeout=10.0)
                response.raise_for_status()
            return True
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            logger.warning(
                "green_coin_post_error attempt=%d url=%s error=%s",
                attempt,
                self._url,
                str(exc),
            )
            return False

    @staticmethod
    def _write_to_retry_log(payload: dict) -> None:
        """Append the event as a single JSON line to the retry log file."""
        with _RETRY_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, default=str) + "\n")
