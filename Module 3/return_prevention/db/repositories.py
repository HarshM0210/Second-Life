"""
return_prevention/db/repositories.py

CRUD helpers for the Return Prevention module's database tables:
- FitProfileRepository
- SellerProfileRepository
- PriceBandProfileRepository
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from return_prevention.db.models import (
    FitProfileRow,
    PriceBandProfileRow,
    SellerProfileRow,
)

logger = logging.getLogger(__name__)

GLOBAL_SELLER_ID = "__global__"


# ---------------------------------------------------------------------------
# FitProfileRepository
# ---------------------------------------------------------------------------


class FitProfileRepository:
    """CRUD helpers for the fit_profile table."""

    @staticmethod
    def insert_pending(
        db: Session,
        customer_id: str,
        brand: str,
        order_id: str,
        purchased_size: str,
    ) -> FitProfileRow:
        """Insert a new fit profile row with status='pending'."""
        row = FitProfileRow(
            customer_id=customer_id,
            brand=brand,
            order_id=order_id,
            purchased_size=purchased_size,
            status="pending",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    @staticmethod
    def mark_returned(
        db: Session,
        order_id: str,
        return_reason: Optional[str] = None,
    ) -> None:
        """
        Transition an order's fit profile row to status='returned'.

        If the order_id is not found, logs a warning and returns without mutation.
        """
        row = (
            db.query(FitProfileRow)
            .filter(FitProfileRow.order_id == order_id)
            .first()
        )
        if row is None:
            logger.warning(
                "mark_returned called with unknown order_id=%s; no mutation performed",
                order_id,
            )
            return

        row.status = "returned"
        row.return_reason = return_reason
        row.updated_at = datetime.now(timezone.utc)
        db.commit()

    @staticmethod
    def mark_kept_bulk(db: Session, cutoff_datetime: datetime) -> int:
        """
        Bulk-update all rows with status='pending' and created_at < cutoff
        to status='kept'.

        Returns the number of rows updated.
        """
        count = (
            db.query(FitProfileRow)
            .filter(
                FitProfileRow.status == "pending",
                FitProfileRow.created_at < cutoff_datetime,
            )
            .update(
                {"status": "kept", "updated_at": datetime.now(timezone.utc)},
                synchronize_session="fetch",
            )
        )
        db.commit()
        return count

    @staticmethod
    def get_by_customer(db: Session, customer_id: str) -> list[FitProfileRow]:
        """Return all FitProfileRow objects for the given customer."""
        return (
            db.query(FitProfileRow)
            .filter(FitProfileRow.customer_id == customer_id)
            .all()
        )

    @staticmethod
    def count(db: Session, customer_id: str, brand: str) -> int:
        """Return the number of fit profile rows for a (customer_id, brand) pair."""
        return (
            db.query(func.count(FitProfileRow.id))
            .filter(
                FitProfileRow.customer_id == customer_id,
                FitProfileRow.brand == brand,
            )
            .scalar()
            or 0
        )


# ---------------------------------------------------------------------------
# SellerProfileRepository
# ---------------------------------------------------------------------------


class SellerProfileRepository:
    """CRUD helpers for the seller_profile table."""

    @staticmethod
    def get(db: Session, seller_id: str) -> Optional[SellerProfileRow]:
        """Fetch a seller profile by seller_id. Returns None if not found."""
        return (
            db.query(SellerProfileRow)
            .filter(SellerProfileRow.seller_id == seller_id)
            .first()
        )

    @staticmethod
    def get_global_mean(db: Session) -> float:
        """
        Fetch the global mean seller return rate from the __global__ sentinel row.

        Returns 0.0 if the sentinel row does not exist (should not happen if
        seed_global_seller was called at startup).
        """
        row = (
            db.query(SellerProfileRow)
            .filter(SellerProfileRow.seller_id == GLOBAL_SELLER_ID)
            .first()
        )
        if row is None:
            logger.warning(
                "Global seller sentinel row ('%s') not found; returning 0.0",
                GLOBAL_SELLER_ID,
            )
            return 0.0
        return row.return_rate

    @staticmethod
    def upsert(
        db: Session,
        seller_id: str,
        return_rate: float,
        total_orders: int,
        total_returns: int,
    ) -> SellerProfileRow:
        """Insert or update a seller profile row."""
        row = (
            db.query(SellerProfileRow)
            .filter(SellerProfileRow.seller_id == seller_id)
            .first()
        )
        if row is None:
            row = SellerProfileRow(
                seller_id=seller_id,
                return_rate=return_rate,
                total_orders=total_orders,
                total_returns=total_returns,
            )
            db.add(row)
        else:
            row.return_rate = return_rate
            row.total_orders = total_orders
            row.total_returns = total_returns
            row.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(row)
        return row


# ---------------------------------------------------------------------------
# PriceBandProfileRepository
# ---------------------------------------------------------------------------


class PriceBandProfileRepository:
    """CRUD helpers for the price_band_profile table."""

    @staticmethod
    def get_high_return_band(db: Session, customer_id: str) -> Optional[str]:
        """
        Return the price band label with the highest return rate for the customer.

        Returns None if no price band profile exists for this customer.
        """
        row = (
            db.query(PriceBandProfileRow)
            .filter(PriceBandProfileRow.customer_id == customer_id)
            .order_by(PriceBandProfileRow.return_rate.desc())
            .first()
        )
        if row is None:
            return None
        return row.price_band

    @staticmethod
    def upsert(
        db: Session,
        customer_id: str,
        price_band: str,
        total_orders: int,
        total_returns: int,
        return_rate: float,
    ) -> PriceBandProfileRow:
        """Insert or update a price band profile row."""
        row = (
            db.query(PriceBandProfileRow)
            .filter(
                PriceBandProfileRow.customer_id == customer_id,
                PriceBandProfileRow.price_band == price_band,
            )
            .first()
        )
        if row is None:
            row = PriceBandProfileRow(
                customer_id=customer_id,
                price_band=price_band,
                total_orders=total_orders,
                total_returns=total_returns,
                return_rate=return_rate,
            )
            db.add(row)
        else:
            row.total_orders = total_orders
            row.total_returns = total_returns
            row.return_rate = return_rate
            row.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(row)
        return row


# ---------------------------------------------------------------------------
# Startup helper
# ---------------------------------------------------------------------------


def seed_global_seller(db: Session) -> None:
    """
    Insert the __global__ sentinel row in seller_profile if it does not already exist.

    This should be called at application startup to ensure the global mean
    fallback is always available.
    """
    existing = (
        db.query(SellerProfileRow)
        .filter(SellerProfileRow.seller_id == GLOBAL_SELLER_ID)
        .first()
    )
    if existing is None:
        global_row = SellerProfileRow(
            seller_id=GLOBAL_SELLER_ID,
            return_rate=0.15,  # reasonable default global mean
            total_orders=0,
            total_returns=0,
        )
        db.add(global_row)
        db.commit()
        logger.info("Seeded global seller sentinel row ('%s')", GLOBAL_SELLER_ID)
    else:
        logger.debug("Global seller sentinel row already exists; skipping seed")
