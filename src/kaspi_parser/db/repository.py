"""Repository layer.

All DB access funnels through these functions. Keeping it thin & explicit
rather than dressing it up as a generic Repo<T> — too much ceremony for a
focused project.

Crucial for speed: we batch-upsert via PostgreSQL's `INSERT ... ON CONFLICT`
instead of doing N round-trips with SQLAlchemy session.add().
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from kaspi_parser.api.schemas import CategoryNode, ProductCard
from kaspi_parser.db.models import Category, ParseJob, Product, ProductSnapshot


# ============================================================================
# Categories
# ============================================================================
async def upsert_categories(
    session: AsyncSession, nodes: Iterable[CategoryNode], *, parent_code: str | None = None
) -> int:
    """Insert or update categories in bulk. Returns number of rows affected."""
    rows: list[dict[str, Any]] = []
    _flatten_nodes(list(nodes), parent_code=parent_code, depth=0, out=rows)
    if not rows:
        return 0

    stmt = pg_insert(Category).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Category.code],
        set_={
            "title": stmt.excluded.title,
            "parent_code": stmt.excluded.parent_code,
            "product_count": stmt.excluded.product_count,
            "popularity": stmt.excluded.popularity,
            "depth": stmt.excluded.depth,
            "is_leaf": stmt.excluded.is_leaf,
            "last_seen_at": func.now(),
        },
    )
    await session.execute(stmt)
    return len(rows)


def _flatten_nodes(
    nodes: list[CategoryNode],
    *,
    parent_code: str | None,
    depth: int,
    out: list[dict[str, Any]],
) -> None:
    for node in nodes:
        out.append(
            {
                "code": node.code,
                "title": node.title_ru or node.title,
                "parent_code": parent_code,
                "product_count": node.count,
                "popularity": node.popularity,
                "depth": depth,
                "is_leaf": not node.items,
            }
        )
        if node.items:
            _flatten_nodes(node.items, parent_code=node.code, depth=depth + 1, out=out)


# ============================================================================
# Products + snapshots
# ============================================================================
async def upsert_products_with_snapshots(
    session: AsyncSession,
    cards: list[ProductCard],
    *,
    city_id: str,
    captured_at: datetime | None = None,
) -> tuple[int, int]:
    """Batch-upsert products and append a snapshot per card.

    Returns (products_upserted, snapshots_inserted).
    """
    if not cards:
        return 0, 0

    when = captured_at or datetime.now(UTC)

    # --- Products (upsert) ---
    product_rows = [
        {
            "id": c.config_sku,
            "title": c.title,
            "brand": c.brand,
            "category_code": _leaf_category_code(c),
            "category_path": c.category_ru or c.category,
            "shop_link": c.shop_link,
            "created_time": _parse_kaspi_time(c.created_time),
        }
        for c in cards
    ]
    prod_stmt = pg_insert(Product).values(product_rows)
    prod_stmt = prod_stmt.on_conflict_do_update(
        index_elements=[Product.id],
        set_={
            "title": prod_stmt.excluded.title,
            "brand": prod_stmt.excluded.brand,
            "category_code": prod_stmt.excluded.category_code,
            "category_path": prod_stmt.excluded.category_path,
            "shop_link": prod_stmt.excluded.shop_link,
            "last_seen_at": func.now(),
        },
    )
    await session.execute(prod_stmt)

    # --- Snapshots (append) ---
    snap_rows = [
        {
            "product_id": c.config_sku,
            "captured_at": when,
            "city_id": city_id,
            "unit_price": c.unit_price,
            "unit_sale_price": c.unit_sale_price,
            "price_before_discount": c.unit_price_before_discount,
            "discount_pct": c.discount,
            "rating": c.rating,
            "reviews_quantity": c.reviews_quantity,
            "stock": c.stock,
            "delivery_duration": c.delivery_duration,
            "best_merchant": c.best_merchant,
            "raw": c.raw,
        }
        for c in cards
    ]
    snap_stmt = pg_insert(ProductSnapshot).values(snap_rows)
    # If a snapshot for this (product_id, captured_at) already exists — update it.
    snap_stmt = snap_stmt.on_conflict_do_update(
        index_elements=[ProductSnapshot.product_id, ProductSnapshot.captured_at],
        set_={
            "unit_price": snap_stmt.excluded.unit_price,
            "unit_sale_price": snap_stmt.excluded.unit_sale_price,
            "price_before_discount": snap_stmt.excluded.price_before_discount,
            "discount_pct": snap_stmt.excluded.discount_pct,
            "rating": snap_stmt.excluded.rating,
            "reviews_quantity": snap_stmt.excluded.reviews_quantity,
            "stock": snap_stmt.excluded.stock,
            "delivery_duration": snap_stmt.excluded.delivery_duration,
            "best_merchant": snap_stmt.excluded.best_merchant,
            "raw": snap_stmt.excluded.raw,
        },
    )
    await session.execute(snap_stmt)

    return len(product_rows), len(snap_rows)


def _leaf_category_code(card: ProductCard) -> str | None:
    """Kaspi puts the leaf category first in `categoryCodes`."""
    return card.category_codes[0] if card.category_codes else None


def _parse_kaspi_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        # Kaspi returns "2024-09-28T15:38:53.495Z"
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        logger.debug("Could not parse kaspi timestamp: {}", value)
        return None


# ============================================================================
# Parse jobs
# ============================================================================
async def create_parse_job(session: AsyncSession, *, city_id: str, categories_planned: int) -> int:
    job = ParseJob(city_id=city_id, categories_planned=categories_planned, status="running")
    session.add(job)
    await session.flush()
    return job.id


async def finish_parse_job(
    session: AsyncSession,
    job_id: int,
    *,
    products_seen: int,
    products_saved: int,
    errors: int,
    status: str = "success",
    notes: str | None = None,
) -> None:
    stmt = select(ParseJob).where(ParseJob.id == job_id)
    job = (await session.execute(stmt)).scalar_one()
    job.finished_at = datetime.now(UTC)
    job.status = status
    job.products_seen = products_seen
    job.products_saved = products_saved
    job.errors = errors
    if notes is not None:
        job.notes = notes


async def bump_categories_done(session: AsyncSession, job_id: int) -> None:
    stmt = select(ParseJob).where(ParseJob.id == job_id)
    job = (await session.execute(stmt)).scalar_one()
    job.categories_done += 1
