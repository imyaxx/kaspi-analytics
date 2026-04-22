"""initial schema with timescale hypertable

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-22
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # categories
    # ------------------------------------------------------------------
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("parent_code", sa.String(length=255), nullable=True),
        sa.Column("product_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("popularity", sa.Integer(), server_default="0", nullable=False),
        sa.Column("depth", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_leaf", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_categories_code", "categories", ["code"])
    op.create_index("ix_categories_parent_code", "categories", ["parent_code"])
    op.create_index("ix_categories_depth", "categories", ["depth"])
    op.create_index("ix_categories_is_leaf", "categories", ["is_leaf"])

    # ------------------------------------------------------------------
    # products
    # ------------------------------------------------------------------
    op.create_table(
        "products",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("brand", sa.String(length=255), nullable=True),
        sa.Column("category_code", sa.String(length=255), nullable=True),
        sa.Column(
            "category_path",
            postgresql.ARRAY(sa.String()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("shop_link", sa.Text(), nullable=True),
        sa.Column("created_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_products_brand", "products", ["brand"])
    op.create_index("ix_products_category_code", "products", ["category_code"])
    # Trigram index for title search
    op.execute(
        "CREATE INDEX ix_products_title_trgm ON products "
        "USING gin (title gin_trgm_ops)"
    )

    # ------------------------------------------------------------------
    # product_snapshots (will become a TimescaleDB hypertable below)
    # ------------------------------------------------------------------
    op.create_table(
        "product_snapshots",
        sa.Column("product_id", sa.String(length=64), nullable=False),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("city_id", sa.String(length=20), nullable=False),
        sa.Column("unit_price", sa.Integer(), nullable=False),
        sa.Column("unit_sale_price", sa.Integer(), nullable=False),
        sa.Column("price_before_discount", sa.Integer(), nullable=True),
        sa.Column("discount_pct", sa.Integer(), nullable=True),
        sa.Column("rating", sa.Float(), server_default="0", nullable=False),
        sa.Column("reviews_quantity", sa.Integer(), server_default="0", nullable=False),
        sa.Column("stock", sa.Integer(), server_default="0", nullable=False),
        sa.Column("delivery_duration", sa.String(length=32), nullable=True),
        sa.Column("best_merchant", sa.String(length=255), nullable=True),
        sa.Column("raw", postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("product_id", "captured_at"),
    )
    op.create_index("ix_snapshots_city", "product_snapshots", ["city_id"])
    op.create_index(
        "ix_snapshots_product_time", "product_snapshots", ["product_id", "captured_at"]
    )
    op.create_index("ix_snapshots_captured_at", "product_snapshots", ["captured_at"])

    # Convert to TimescaleDB hypertable (7-day chunks).
    op.execute(
        "SELECT create_hypertable("
        "'product_snapshots', 'captured_at', "
        "chunk_time_interval => INTERVAL '7 days', "
        "if_not_exists => TRUE"
        ")"
    )

    # ------------------------------------------------------------------
    # parse_jobs
    # ------------------------------------------------------------------
    op.create_table(
        "parse_jobs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="running", nullable=False),
        sa.Column("city_id", sa.String(length=20), nullable=False),
        sa.Column(
            "categories_planned", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column("categories_done", sa.Integer(), server_default="0", nullable=False),
        sa.Column("products_seen", sa.Integer(), server_default="0", nullable=False),
        sa.Column("products_saved", sa.Integer(), server_default="0", nullable=False),
        sa.Column("errors", sa.Integer(), server_default="0", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", name="uq_parse_jobs_id"),
    )
    op.create_index("ix_parse_jobs_status", "parse_jobs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_parse_jobs_status", table_name="parse_jobs")
    op.drop_table("parse_jobs")

    op.drop_index("ix_snapshots_captured_at", table_name="product_snapshots")
    op.drop_index("ix_snapshots_product_time", table_name="product_snapshots")
    op.drop_index("ix_snapshots_city", table_name="product_snapshots")
    op.drop_table("product_snapshots")

    op.execute("DROP INDEX IF EXISTS ix_products_title_trgm")
    op.drop_index("ix_products_category_code", table_name="products")
    op.drop_index("ix_products_brand", table_name="products")
    op.drop_table("products")

    op.drop_index("ix_categories_is_leaf", table_name="categories")
    op.drop_index("ix_categories_depth", table_name="categories")
    op.drop_index("ix_categories_parent_code", table_name="categories")
    op.drop_index("ix_categories_code", table_name="categories")
    op.drop_table("categories")
