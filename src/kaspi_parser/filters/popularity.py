"""Popularity filter.

Drops products that don't meet minimum thresholds so the DB stays focused on
SKUs actually worth tracking.
"""

from __future__ import annotations

from collections.abc import Iterable

from kaspi_parser.api.schemas import ProductCard
from kaspi_parser.config import PopularitySettings


class PopularityFilter:
    """Decides whether a product is 'popular enough' to persist."""

    def __init__(self, settings: PopularitySettings) -> None:
        self._settings = settings

    def accepts(self, card: ProductCard) -> bool:
        """Return True when `card` clears all configured thresholds."""
        s = self._settings

        if card.reviews_quantity < s.min_reviews:
            return False
        if card.rating < s.min_rating:
            return False
        if s.require_in_stock and card.stock <= 0:
            return False
        return True

    def filter(self, cards: Iterable[ProductCard]) -> list[ProductCard]:
        """Return only the cards that pass `accepts()`."""
        return [c for c in cards if self.accepts(c)]
