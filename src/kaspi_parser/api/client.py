"""High-level Kaspi API client.

Wraps `HttpClient` + endpoint definitions + schema parsing so that callers
speak in domain terms ("give me page N of category X") instead of URLs and
dicts.
"""

from __future__ import annotations

from typing import Self

from loguru import logger

from kaspi_parser.api.endpoints import FiltersQuery, ResultsQuery, offers_path
from kaspi_parser.api.schemas import (
    FiltersResponse,
    OffersResponse,
    ResultsResponse,
)
from kaspi_parser.config import HttpSettings
from kaspi_parser.core.exceptions import ParsingError
from kaspi_parser.core.http_client import HttpClient


class KaspiClient:
    """Domain-level client for Kaspi endpoints."""

    def __init__(self, http_settings: HttpSettings) -> None:
        self._http = HttpClient(http_settings)

    async def __aenter__(self) -> Self:
        await self._http.__aenter__()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self._http.__aexit__(*exc_info)  # type: ignore[arg-type]

    # -- category tree + first page ----------------------------------------

    async def fetch_filters(
        self, category_code: str, *, city_id: str, sort: str = "relevance"
    ) -> FiltersResponse:
        """Fetch the filters endpoint: first 12 cards + full subtree + total."""
        query = FiltersQuery(category_code=category_code, city_id=city_id, sort=sort)
        raw = await self._http.get_json(query.path, params=query.params)
        try:
            return FiltersResponse.model_validate(raw)
        except Exception as e:  # pydantic validation error
            logger.error("Failed to parse filters for {}: {}", category_code, e)
            raise ParsingError(f"Invalid filters response for {category_code}") from e

    # -- pagination ---------------------------------------------------------

    async def fetch_results_page(
        self,
        category_code: str,
        *,
        city_id: str,
        page: int,
        sort: str = "relevance",
    ) -> ResultsResponse:
        """Fetch a single page from the results endpoint.

        Note: `page=0` is the second page (the first lives inside `filters`).
        """
        query = ResultsQuery(
            category_code=category_code, city_id=city_id, page=page, sort=sort
        )
        raw = await self._http.get_json(query.path, params=query.params)
        try:
            return ResultsResponse.model_validate(raw)
        except Exception as e:
            logger.error("Failed to parse results p={} for {}: {}", page, category_code, e)
            raise ParsingError(f"Invalid results response for {category_code}") from e

    # -- competitor offers (for future autopricing) ------------------------

    async def fetch_offers(self, master_sku: str) -> OffersResponse:
        raw = await self._http.get_json(offers_path(master_sku))
        try:
            return OffersResponse.model_validate(raw)
        except Exception as e:
            logger.error("Failed to parse offers for {}: {}", master_sku, e)
            raise ParsingError(f"Invalid offers response for {master_sku}") from e
