"""Category tree parser.

For each whitelisted category entry, we ask Kaspi for the `filters` endpoint.
The response carries the full `treeCategory` subtree for that root, which we
flatten into DB rows and return as a list of target categories to crawl.
"""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kaspi_parser.api.client import KaspiClient
from kaspi_parser.api.schemas import CategoryNode
from kaspi_parser.config import CategoryEntry, Settings
from kaspi_parser.db import repository as repo


@dataclass(frozen=True, slots=True)
class CrawlTarget:
    """A concrete category we intend to crawl.

    `code` is the Kaspi category code; `total` is Kaspi's own total count
    for that category (used to cap pagination and order work).
    """

    code: str
    title: str
    total: int
    depth: int


class CategoryTreeParser:
    """Resolves whitelisted config entries into concrete crawl targets."""

    def __init__(
        self,
        client: KaspiClient,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
    ) -> None:
        self._client = client
        self._session_factory = session_factory
        self._settings = settings

    async def build_targets(self) -> list[CrawlTarget]:
        """For every whitelist entry: fetch its subtree, persist, pick targets."""
        targets: list[CrawlTarget] = []

        for entry in self._settings.categories.whitelist:
            logger.info("Resolving subtree for '{}' (code={})", entry.title, entry.code)
            root_node = await self._fetch_root(entry)
            if root_node is None:
                logger.warning("No tree returned for {}", entry.code)
                continue

            # Persist the subtree so we have a snapshot of Kaspi's taxonomy.
            async with self._session_factory() as session:
                async with session.begin():
                    await repo.upsert_categories(session, [root_node])

            # Pick which nodes to actually crawl based on config.
            picked = self._pick_targets(root_node, entry)
            targets.extend(picked)

            logger.info(
                "  → {} target categories from '{}' ({} total products)",
                len(picked),
                entry.title,
                sum(t.total for t in picked),
            )

        # Largest first — helps surface problems early.
        targets.sort(key=lambda t: t.total, reverse=True)
        return targets

    # -- internals ---------------------------------------------------------

    async def _fetch_root(self, entry: CategoryEntry) -> CategoryNode | None:
        resp = await self._client.fetch_filters(
            entry.code, city_id=self._settings.city.id
        )
        tree = resp.data.tree_category
        if tree is None or not tree.items:
            return None
        # The tree from Kaspi is usually a single-root list.
        return tree.items[0]

    def _pick_targets(
        self, root: CategoryNode, entry: CategoryEntry
    ) -> list[CrawlTarget]:
        """Decide which subtree nodes become crawl targets.

        Strategy:
        - `nested: true` → every leaf under the root.
        - `nested: false` → if root has leaves, crawl those leaves;
                            otherwise crawl the root itself.
        """
        if entry.nested:
            nodes = root.leaves()
        else:
            nodes = root.leaves() if root.items else [root]

        return [
            CrawlTarget(
                code=n.code,
                title=n.title_ru or n.title,
                total=n.count,
                depth=0,  # depth is mostly informational here
            )
            for n in nodes
            if n.count > 0
        ]
