"""Product parser.

For each `CrawlTarget`:
  1. Fetch the `filters` endpoint (page 0 → 12 cards + total).
  2. Compute how many more pages to fetch (capped by config).
  3. Fetch the rest from `results` in parallel, preserving order.
  4. Filter cards through `PopularityFilter`.
  5. Bulk-save survivors as one product + one snapshot each.

Parallelism is bounded by the rate limiter inside `HttpClient` plus an
asyncio.Semaphore so we never have more than N inflight per target.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kaspi_parser.api.client import KaspiClient
from kaspi_parser.api.schemas import ProductCard
from kaspi_parser.config import Settings
from kaspi_parser.core.exceptions import EndOfResultsError
from kaspi_parser.db import repository as repo
from kaspi_parser.filters.popularity import PopularityFilter
from kaspi_parser.parsers.category_tree import CrawlTarget


@dataclass(slots=True)
class CategoryStats:
    """Per-category summary after crawling."""

    code: str
    title: str
    seen: int = 0
    saved: int = 0
    pages_fetched: int = 0
    errors: int = 0


@dataclass(slots=True)
class CrawlReport:
    """Aggregate result of a full parse run."""

    started_at: datetime
    finished_at: datetime | None = None
    per_category: list[CategoryStats] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.per_category is None:
            self.per_category = []

    @property
    def total_seen(self) -> int:
        return sum(c.seen for c in self.per_category)

    @property
    def total_saved(self) -> int:
        return sum(c.saved for c in self.per_category)

    @property
    def total_errors(self) -> int:
        return sum(c.errors for c in self.per_category)


class ProductParser:
    """Crawls products across a list of targets and persists survivors."""

    def __init__(
        self,
        client: KaspiClient,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
    ) -> None:
        self._client = client
        self._session_factory = session_factory
        self._settings = settings
        self._popularity = PopularityFilter(settings.popularity)

    # -- public entrypoint -------------------------------------------------

    async def crawl(self, targets: list[CrawlTarget]) -> CrawlReport:
        report = CrawlReport(started_at=datetime.now(UTC))

        for idx, target in enumerate(targets, start=1):
            logger.info(
                "[{}/{}] '{}' — total {} products",
                idx,
                len(targets),
                target.title,
                target.total,
            )
            stats = await self._crawl_target(target)
            report.per_category.append(stats)
            logger.info(
                "    ↳ saved {}/{} (popular/seen), pages={}, errors={}",
                stats.saved,
                stats.seen,
                stats.pages_fetched,
                stats.errors,
            )

        report.finished_at = datetime.now(UTC)
        return report

    # -- per-category logic ------------------------------------------------

    async def _crawl_target(self, target: CrawlTarget) -> CategoryStats:
        stats = CategoryStats(code=target.code, title=target.title)

        # Step 1: page 0 via filters (gets total + first 12 cards).
        try:
            first = await self._client.fetch_filters(
                target.code, city_id=self._settings.city.id
            )
        except Exception as e:
            logger.error("filters failed for {}: {}", target.code, e)
            stats.errors += 1
            return stats

        stats.pages_fetched = 1
        first_cards = first.data.cards
        total = first.data.total or target.total

        # Persist page 0's popular cards immediately.
        await self._persist_cards(first_cards, stats)

        # Step 2: figure out remaining pages.
        page_size = self._settings.pagination.page_size
        max_pages = self._settings.pagination.max_pages_per_query

        total_pages_available = (total + page_size - 1) // page_size
        # Kaspi caps results around 5000 — don't bother beyond that.
        pages_to_fetch = min(total_pages_available - 1, max_pages - 1)

        if pages_to_fetch <= 0:
            return stats

        # Step 3: fetch pages 1..N in parallel (page is 0-based for results endpoint).
        await self._fetch_pages_in_parallel(target, pages_to_fetch, stats)
        return stats

    async def _fetch_pages_in_parallel(
        self, target: CrawlTarget, pages_to_fetch: int, stats: CategoryStats
    ) -> None:
        """Fetch pages concurrently, bounded by a semaphore."""
        sem = asyncio.Semaphore(self._settings.http.max_concurrent)
        empty_streak = 0
        empty_lock = asyncio.Lock()
        stop_event = asyncio.Event()

        async def fetch_one(page: int) -> list[ProductCard]:
            nonlocal empty_streak
            if stop_event.is_set():
                return []
            async with sem:
                if stop_event.is_set():
                    return []
                try:
                    # `results` uses page=0 for the second page.
                    resp = await self._client.fetch_results_page(
                        target.code,
                        city_id=self._settings.city.id,
                        page=page - 1,
                    )
                    cards = resp.data
                except EndOfResultsError:
                    # Kaspi's hard cap (~5000 items). Stop the whole category.
                    stop_event.set()
                    return []
                except Exception as e:
                    logger.warning("page {} failed for {}: {}", page, target.code, e)
                    stats.errors += 1
                    return []

            # Track consecutive empty pages to bail out early.
            async with empty_lock:
                if not cards:
                    empty_streak += 1
                    if empty_streak >= self._settings.pagination.stop_on_empty_pages:
                        stop_event.set()
                else:
                    empty_streak = 0

            return cards

        tasks = [asyncio.create_task(fetch_one(p)) for p in range(1, pages_to_fetch + 1)]
        try:
            pages = await asyncio.gather(*tasks)
        finally:
            for t in tasks:
                if not t.done():
                    t.cancel()

        for cards in pages:
            if cards:
                stats.pages_fetched += 1
                await self._persist_cards(cards, stats)

    # -- persistence -------------------------------------------------------

    async def _persist_cards(
        self, cards: list[ProductCard], stats: CategoryStats
    ) -> None:
        stats.seen += len(cards)
        popular = self._popularity.filter(cards)
        if not popular:
            return

        try:
            async with self._session_factory() as session:
                async with session.begin():
                    prods, _snaps = await repo.upsert_products_with_snapshots(
                        session,
                        popular,
                        city_id=self._settings.city.id,
                    )
            stats.saved += prods
        except Exception as e:
            logger.exception("DB save failed for {}: {}", stats.code, e)
            stats.errors += 1