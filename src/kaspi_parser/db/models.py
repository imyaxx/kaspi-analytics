"""SQLAlchemy ORM models.

Design notes:
- `products` — one row per Kaspi product (configSku is the natural key).
- `product_snapshots` — time-series of price/stock/rating/reviews. Stored as a
  TimescaleDB hypertable so time-range queries stay fast as data grows.
- `categories` — denormalised flat table of categories we've seen.
- `parse_jobs` — audit log of runs for observability.

All timestamps are stored in UTC.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for all models."""


# ============================================================================
# Categories
# ============================================================================
class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(512))
    parent_code: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    product_count: Mapped[int] = mapped_column(Integer, default=0)
    popularity: Mapped[int] = mapped_column(Integer, default=0)
    depth: Mapped[int] = mapped_column(Integer, default=0, index=True)
    is_leaf: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ============================================================================
# Products
# ============================================================================
class Product(Base):
    __tablename__ = "products"

    # `configSku` is the stable product id in Kaspi's world.
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    brand: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    category_code: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    category_path: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    shop_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    snapshots: Mapped[list["ProductSnapshot"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_products_title_trgm", "title", postgresql_using="gin",
              postgresql_ops={"title": "gin_trgm_ops"}),
    )


# ============================================================================
# Snapshots — time-series (TimescaleDB hypertable, see migrations)
# ============================================================================
class ProductSnapshot(Base):
    __tablename__ = "product_snapshots"

    # Composite primary key: TimescaleDB requires the time column in PK.
    product_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("products.id", ondelete="CASCADE"), primary_key=True
    )
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, server_default=func.now()
    )

    city_id: Mapped[str] = mapped_column(String(20), index=True)

    unit_price: Mapped[int] = mapped_column(Integer)
    unit_sale_price: Mapped[int] = mapped_column(Integer)
    price_before_discount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    discount_pct: Mapped[int | None] = mapped_column(Integer, nullable=True)

    rating: Mapped[float] = mapped_column(Float, default=0.0)
    reviews_quantity: Mapped[int] = mapped_column(Integer, default=0)

    stock: Mapped[int] = mapped_column(Integer, default=0)
    delivery_duration: Mapped[str | None] = mapped_column(String(32), nullable=True)

    best_merchant: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Full payload for future reprocessing without re-crawling.
    raw: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    product: Mapped[Product] = relationship(back_populates="snapshots")

    __table_args__ = (
        Index("ix_snapshots_product_time", "product_id", "captured_at"),
        Index("ix_snapshots_captured_at", "captured_at"),
    )


# ============================================================================
# Parse jobs — audit trail
# ============================================================================
class ParseJob(Base):
    __tablename__ = "parse_jobs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="running", index=True)

    city_id: Mapped[str] = mapped_column(String(20))

    categories_planned: Mapped[int] = mapped_column(Integer, default=0)
    categories_done: Mapped[int] = mapped_column(Integer, default=0)
    products_seen: Mapped[int] = mapped_column(Integer, default=0)
    products_saved: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[int] = mapped_column(Integer, default=0)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("id", name="uq_parse_jobs_id"),
    )
