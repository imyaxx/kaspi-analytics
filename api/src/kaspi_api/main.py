"""Kaspi Analytics API.

A thin FastAPI layer over the same Postgres database the parser fills.
One purpose: feed the web dashboard with product rows — filtered, sorted,
paginated — and category lists.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated, Any, Literal

import asyncpg
import orjson
from fastapi import Depends, FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from kaspi_parser.config import load_settings

# ----------------------------------------------------------------------------
# Lifespan — open/close the asyncpg pool once per process
# ----------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()
    db = settings.database
    pool = await asyncpg.create_pool(
        host=db.host,
        port=db.port,
        database=db.name,
        user=db.user,
        password=db.password,
        min_size=2,
        max_size=10,
    )
    app.state.pool = pool
    try:
        yield
    finally:
        await pool.close()


app = FastAPI(
    title="Kaspi Analytics API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — the web dashboard is served separately during dev (Vite on :5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----------------------------------------------------------------------------
# Dependencies
# ----------------------------------------------------------------------------
async def get_conn(request: Request):
    async with request.app.state.pool.acquire() as conn:
        yield conn


Conn = Annotated[asyncpg.Connection, Depends(get_conn)]


# ----------------------------------------------------------------------------
# Response models
# ----------------------------------------------------------------------------
class CategoryOut(BaseModel):
    code: str
    title: str
    product_count: int


class ProductOut(BaseModel):
    id: str
    title: str
    brand: str | None
    category_code: str | None
    category_title: str | None
    price: int
    price_before_discount: int | None
    discount_pct: int | None
    rating: float
    reviews: int
    stock: int
    best_merchant: str | None
    image_url: str | None
    kaspi_url: str
    shop_link: str | None


class ProductsResponse(BaseModel):
    items: list[ProductOut]
    total: int
    limit: int
    offset: int


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
SORT_FIELDS: dict[str, str] = {
    "reviews": "s.reviews_quantity",
    "rating": "s.rating",
    "price": "s.unit_sale_price",
    "title": "p.title",
}


def _kaspi_url(product_id: str) -> str:
    return f"https://kaspi.kz/shop/p/-{product_id}/"


def _image_url(raw: Any) -> str | None:
    """Kaspi puts preview images in `previewImages[0].medium` usually.

    `raw` may arrive as dict (JSONB auto-decoded), str (JSON string),
    bytes, or None — handle all cases defensively.
    """
    if raw is None:
        return None

    if isinstance(raw, (str, bytes)):
        try:
            raw = orjson.loads(raw)
        except (orjson.JSONDecodeError, ValueError):
            return None

    if not isinstance(raw, dict):
        return None

    previews = raw.get("previewImages") or []
    if previews and isinstance(previews, list):
        first = previews[0]
        if isinstance(first, dict):
            return first.get("medium") or first.get("small") or first.get("large")
    # fallbacks seen in Kaspi payloads
    return raw.get("image") or raw.get("previewImage")


# ----------------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------------
@app.get("/api/health")
async def health(conn: Conn) -> dict[str, Any]:
    total = await conn.fetchval("SELECT count(*) FROM products")
    return {"status": "ok", "products": total}


@app.get("/api/categories", response_model=list[CategoryOut])
async def categories(conn: Conn) -> list[CategoryOut]:
    """Return only categories that actually have saved (popular) products."""
    rows = await conn.fetch(
        """
        SELECT c.code,
               c.title,
               count(DISTINCT p.id) AS product_count
        FROM categories c
        JOIN products p ON p.category_code = c.code
        GROUP BY c.code, c.title
        HAVING count(DISTINCT p.id) > 0
        ORDER BY product_count DESC
        """
    )
    return [CategoryOut(**dict(r)) for r in rows]


@app.get("/api/products", response_model=ProductsResponse)
async def products(
    conn: Conn,
    category: str | None = Query(default=None, description="Kaspi category code"),
    q: str | None = Query(default=None, description="Search in title"),
    min_price: int | None = Query(default=None, ge=0),
    max_price: int | None = Query(default=None, ge=0),
    min_rating: float | None = Query(default=None, ge=0, le=5),
    min_reviews: int | None = Query(default=None, ge=0),
    sort_by: Literal["reviews", "rating", "price", "title"] = "reviews",
    sort_dir: Literal["asc", "desc"] = "desc",
    limit: int = Query(default=50, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
) -> ProductsResponse:
    """Latest snapshot per product, with filters + sorting + pagination."""
    where: list[str] = []
    params: list[Any] = []

    def add(cond: str, *values: Any) -> None:
        for v in values:
            params.append(v)
        where.append(cond.format(*[f"${len(params) - len(values) + i + 1}" for i in range(len(values))]))

    if category:
        add("p.category_code = {0}", category)
    if q:
        add("p.title ILIKE {0}", f"%{q}%")
    if min_price is not None:
        add("s.unit_sale_price >= {0}", min_price)
    if max_price is not None:
        add("s.unit_sale_price <= {0}", max_price)
    if min_rating is not None:
        add("s.rating >= {0}", min_rating)
    if min_reviews is not None:
        add("s.reviews_quantity >= {0}", min_reviews)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    sort_col = SORT_FIELDS[sort_by]
    sort_sql = f"{sort_col} {sort_dir.upper()} NULLS LAST"

    # Latest snapshot per product via DISTINCT ON
    base_cte = f"""
        WITH latest AS (
            SELECT DISTINCT ON (s.product_id)
                   s.product_id,
                   s.unit_sale_price,
                   s.price_before_discount,
                   s.discount_pct,
                   s.rating,
                   s.reviews_quantity,
                   s.stock,
                   s.best_merchant,
                   s.raw
            FROM product_snapshots s
            ORDER BY s.product_id, s.captured_at DESC
        )
        SELECT p.id, p.title, p.brand, p.category_code,
               c.title AS category_title,
               s.unit_sale_price AS price,
               s.price_before_discount,
               s.discount_pct,
               s.rating,
               s.reviews_quantity AS reviews,
               s.stock,
               s.best_merchant,
               s.raw,
               p.shop_link
        FROM products p
        JOIN latest s ON s.product_id = p.id
        LEFT JOIN categories c ON c.code = p.category_code
        {where_sql}
    """

    count_sql = f"SELECT count(*) FROM ({base_cte}) x"
    total = await conn.fetchval(count_sql, *params)

    data_sql = (
        base_cte
        + f"\nORDER BY {sort_sql}\nLIMIT ${len(params) + 1} OFFSET ${len(params) + 2}"
    )
    rows = await conn.fetch(data_sql, *params, limit, offset)

    items = [
        ProductOut(
            id=r["id"],
            title=r["title"],
            brand=r["brand"],
            category_code=r["category_code"],
            category_title=r["category_title"],
            price=r["price"],
            price_before_discount=r["price_before_discount"],
            discount_pct=r["discount_pct"],
            rating=r["rating"],
            reviews=r["reviews"],
            stock=r["stock"],
            best_merchant=r["best_merchant"],
            image_url=_image_url(r["raw"]),
            kaspi_url=_kaspi_url(r["id"]),
            shop_link=r["shop_link"],
        )
        for r in rows
    ]

    return ProductsResponse(items=items, total=total or 0, limit=limit, offset=offset)


@app.get("/api/stats")
async def stats(conn: Conn) -> dict[str, Any]:
    """High-level numbers for the dashboard header."""
    total_products = await conn.fetchval("SELECT count(*) FROM products")
    total_categories = await conn.fetchval(
        "SELECT count(DISTINCT category_code) FROM products WHERE category_code IS NOT NULL"
    )
    last_job = await conn.fetchrow(
        "SELECT started_at, finished_at, products_saved, products_seen "
        "FROM parse_jobs ORDER BY id DESC LIMIT 1"
    )
    return {
        "total_products": total_products or 0,
        "total_categories": total_categories or 0,
        "last_run": dict(last_job) if last_job else None,
    }