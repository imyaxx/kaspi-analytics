"""Pydantic models for Kaspi API responses.

We intentionally parse only the fields we actually use downstream. Pydantic is
configured to ignore extras, so Kaspi adding new fields won't break us.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    """Common config: tolerate extras, allow population by field name."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True, frozen=False)


# ============================================================================
# Category tree (inside filters response)
# ============================================================================
class CategoryNode(_Base):
    """One node of Kaspi's `treeCategory`.

    `id` looks like ":category:Smartphones" — the code lives after the colon.
    `count` is total SKUs in this category; `popularity` reflects Kaspi's
    internal weighting.
    """

    id: str
    title: str
    title_ru: str | None = Field(default=None, alias="titleRu")
    link: str | None = None
    count: int = 0
    popularity: int = 0
    active: bool = False
    expanded: bool = True
    items: list[CategoryNode] = Field(default_factory=list)

    @property
    def code(self) -> str:
        """Extract `Smartphones` from `:category:Smartphones`."""
        prefix = ":category:"
        return self.id[len(prefix):] if self.id.startswith(prefix) else self.id

    def walk(self) -> list[CategoryNode]:
        """Flatten the subtree into a list (self + descendants)."""
        out: list[CategoryNode] = [self]
        for child in self.items:
            out.extend(child.walk())
        return out

    def leaves(self) -> list[CategoryNode]:
        """Return only nodes that have no children."""
        if not self.items:
            return [self]
        result: list[CategoryNode] = []
        for child in self.items:
            result.extend(child.leaves())
        return result


class TreeCategory(_Base):
    items: list[CategoryNode] = Field(default_factory=list)


# ============================================================================
# Product card
# ============================================================================
class ProductCard(_Base):
    """Single product card from `cards[]`.

    Kaspi's shape is messy — we keep fields we actually analyse, plus the
    raw payload for future needs (stored as JSONB in Postgres).
    """

    # Identity
    id: str
    config_sku: str = Field(alias="configSku")
    title: str
    brand: str | None = None
    category_id: str | None = Field(default=None, alias="categoryId")

    # Pricing
    unit_price: int = Field(alias="unitPrice")
    unit_sale_price: int = Field(alias="unitSalePrice")
    unit_price_before_discount: int | None = Field(default=None, alias="unitPriceBeforeDiscount")
    discount: int | None = None
    price_minus_bonus: int | None = Field(default=None, alias="priceMinusBonus")

    # Social proof (the core popularity signal)
    rating: float = 0.0
    reviews_quantity: int = Field(default=0, alias="reviewsQuantity")

    # Availability
    stock: int = 0
    delivery_duration: str | None = Field(default=None, alias="deliveryDuration")

    # Taxonomy
    category: list[str] = Field(default_factory=list)
    category_ru: list[str] = Field(default_factory=list, alias="categoryRu")
    category_codes: list[str] = Field(default_factory=list, alias="categoryCodes")

    # Merchants
    best_merchant: str | None = Field(default=None, alias="bestMerchant")
    major_merchants: list[str] = Field(default_factory=list, alias="majorMerchants")

    # Links & meta
    shop_link: str | None = Field(default=None, alias="shopLink")
    created_time: str | None = Field(default=None, alias="createdTime")

    # Raw payload — preserved for JSONB storage
    raw: dict[str, Any] | None = None


# ============================================================================
# Filters response (first page) and Results response (subsequent pages)
# ============================================================================
class FiltersData(_Base):
    """Payload inside `{"data": {...}}` for the filters endpoint."""

    cards: list[ProductCard] = Field(default_factory=list)
    total: int = 0
    title: str | None = None
    category_id: str | None = Field(default=None, alias="categoryId")
    tree_category: TreeCategory | None = Field(default=None, alias="treeCategory")
    limit: int = 12


class FiltersResponse(_Base):
    data: FiltersData


class ResultsResponse(_Base):
    """The `results` endpoint returns `data` as a flat list of cards
    (unlike `filters` which wraps them in an object)."""

    data: list[ProductCard] = Field(default_factory=list)


# ============================================================================
# Offers response (used later for autopricing)
# ============================================================================
class OfferEntry(_Base):
    merchant_id: str = Field(alias="merchantId")
    merchant_name: str = Field(alias="merchantName")
    merchant_rating: float | None = Field(default=None, alias="merchantRating")
    price: int
    delivery_type: str | None = Field(default=None, alias="deliveryType")


class OffersData(_Base):
    offers: list[OfferEntry] = Field(default_factory=list)
    total: int = 0


class OffersResponse(_Base):
    data: OffersData


# Resolve forward reference for CategoryNode.items
CategoryNode.model_rebuild()