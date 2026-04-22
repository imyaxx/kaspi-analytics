"""Kaspi internal API endpoints.

All paths and query-string builders live here so that the rest of the code
doesn't repeat URL literals. If Kaspi changes a path, you edit exactly one file.
"""

from __future__ import annotations

from dataclasses import dataclass

# Reverse-engineered endpoints (April 2026):
#   1) /yml/product-view/pl/filters  — first page of a category + full tree + filters
#   2) /yml/product-view/pl/results  — subsequent pages (pagination)
#   3) /yml/offer-view/offers/{sku}  — all sellers for a given master SKU

FILTERS_PATH = "/yml/product-view/pl/filters"
RESULTS_PATH = "/yml/product-view/pl/results"
OFFERS_PATH_TEMPLATE = "/yml/offer-view/offers/{sku}"


def category_query(
    category_code: str,
    *,
    zone: str = "Magnum_ZONE1",
) -> str:
    """Build the `q=` value for a given category code.

    Format: `:availableInZones:<zone>:category:<code>`
    """
    return f":availableInZones:{zone}:category:{category_code}"


@dataclass(frozen=True, slots=True)
class FiltersQuery:
    """First-page request: returns 12 cards + tree + filters + total."""

    category_code: str
    city_id: str
    sort: str = "relevance"
    zone: str = "Magnum_ZONE1"

    @property
    def path(self) -> str:
        return FILTERS_PATH

    @property
    def params(self) -> dict[str, str]:
        return {
            "q": category_query(self.category_code, zone=self.zone),
            "text": "",
            "all": "false",
            "sort": self.sort,
            "ui": "d",
            "i": "-1",
            "c": self.city_id,
        }


@dataclass(frozen=True, slots=True)
class ResultsQuery:
    """Subsequent pages. `page` is 0-based (page=0 is the second page)."""

    category_code: str
    city_id: str
    page: int
    sort: str = "relevance"
    zone: str = "Magnum_ZONE1"

    @property
    def path(self) -> str:
        return RESULTS_PATH

    @property
    def params(self) -> dict[str, str]:
        return {
            "page": str(self.page),
            "q": category_query(self.category_code, zone=self.zone),
            "text": "",
            "sort": self.sort,
            "qs": "",
            "ui": "d",
            "i": "-1",
            "c": self.city_id,
        }


def offers_path(master_sku: str) -> str:
    """Build the offers endpoint path for a master SKU."""
    return OFFERS_PATH_TEMPLATE.format(sku=master_sku)