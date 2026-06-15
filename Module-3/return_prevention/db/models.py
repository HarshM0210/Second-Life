"""
return_prevention/db/models.py

ORM models for the Return Prevention module's local database:
- FitProfileRow: tracks per-order fit/sizing data and return status
- SellerProfileRow: aggregated seller return metrics
- PriceBandProfileRow: per-customer return rates bucketed by price band
"""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    func,
)

from return_prevention.db.database import Base


class FitProfileRow(Base):
    """Tracks individual order fit profiles for return-risk prediction."""

    __tablename__ = "fit_profile"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(String, nullable=False)
    brand = Column(String, nullable=False)
    order_id = Column(String, nullable=False, unique=True)
    purchased_size = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pending")
    return_reason = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'kept', 'returned')",
            name="ck_fit_profile_status",
        ),
        Index("idx_fit_profile_customer_brand", "customer_id", "brand"),
        Index("idx_fit_profile_order_id", "order_id"),
        Index("idx_fit_profile_status_age", "status", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<FitProfileRow(id={self.id}, customer_id={self.customer_id!r}, "
            f"brand={self.brand!r}, order_id={self.order_id!r}, status={self.status!r})>"
        )


class SellerProfileRow(Base):
    """Aggregated return metrics per seller."""

    __tablename__ = "seller_profile"

    seller_id = Column(String, primary_key=True)
    return_rate = Column(Float, nullable=False)
    total_orders = Column(Integer, nullable=False, default=0)
    total_returns = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint(
            "return_rate >= 0.0 AND return_rate <= 1.0",
            name="ck_seller_profile_return_rate",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<SellerProfileRow(seller_id={self.seller_id!r}, "
            f"return_rate={self.return_rate}, total_orders={self.total_orders})>"
        )


class PriceBandProfileRow(Base):
    """Per-customer return rates bucketed by price band."""

    __tablename__ = "price_band_profile"

    customer_id = Column(String, primary_key=True)
    price_band = Column(String, primary_key=True)
    total_orders = Column(Integer, nullable=False, default=0)
    total_returns = Column(Integer, nullable=False, default=0)
    return_rate = Column(Float, nullable=False, default=0.0)
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint(
            "price_band IN ('0-500', '501-2000', '2001-10000', '10000+')",
            name="ck_price_band_profile_band",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<PriceBandProfileRow(customer_id={self.customer_id!r}, "
            f"price_band={self.price_band!r}, return_rate={self.return_rate})>"
        )
