"""Async HTTP client tuned for Kaspi.

Responsibilities:
- Keep concurrency and throughput within polite bounds (aiolimiter + semaphore)
- Rotate User-Agents and carry browser-like headers
- Retry transient failures with exponential backoff + jitter (tenacity)
- Parse JSON fast (orjson)

Nothing Kaspi-specific lives here beyond headers. Endpoint knowledge lives in
`kaspi_parser.api`.
"""

from __future__ import annotations

import random
from types import TracebackType
from typing import Any, Self

import httpx
import orjson
from aiolimiter import AsyncLimiter
from loguru import logger
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from kaspi_parser.config import HttpSettings
from kaspi_parser.core.exceptions import KaspiApiError, RateLimitedError

# Status codes we'll retry on.
_RETRY_STATUSES = {408, 425, 429, 500, 502, 503, 504}


class HttpClient:
    """Async HTTP client with built-in rate limiting and retries.

    Use as an async context manager:

        async with HttpClient(settings.http) as http:
            data = await http.get_json("/yml/.../pl/filters", params={...})
    """

    def __init__(self, settings: HttpSettings) -> None:
        self._settings = settings
        # Leaky-bucket rate limiter: N requests per 1 second.
        self._limiter = AsyncLimiter(
            max_rate=settings.requests_per_second, time_period=1.0
        )
        self._client: httpx.AsyncClient | None = None

    # -- lifecycle ----------------------------------------------------------

    async def __aenter__(self) -> Self:
        limits = httpx.Limits(
            max_connections=self._settings.max_concurrent * 2,
            max_keepalive_connections=self._settings.max_concurrent,
        )
        timeout = httpx.Timeout(self._settings.timeout_seconds)

        self._client = httpx.AsyncClient(
            base_url=self._settings.base_url,
            http2=True,
            limits=limits,
            timeout=timeout,
            follow_redirects=True,
            headers=self._base_headers(),
        )
        logger.debug("HttpClient opened: base={}", self._settings.base_url)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            logger.debug("HttpClient closed")

    # -- public API ---------------------------------------------------------

    async def get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """GET `url` and return parsed JSON. Retries transient errors."""
        if self._client is None:
            raise RuntimeError("HttpClient used outside of `async with`")

        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self._settings.retries),
                wait=wait_exponential_jitter(
                    initial=self._settings.backoff_base,
                    max=self._settings.backoff_max,
                ),
                retry=retry_if_exception_type((httpx.TransportError, RateLimitedError)),
                reraise=True,
            ):
                with attempt:
                    return await self._do_get_json(url, params=params, headers=headers)
        except RetryError as e:
            raise KaspiApiError(f"Exhausted retries for {url}") from e

        # unreachable; satisfies type checker
        raise KaspiApiError(f"Unreachable: {url}")

    # -- internals ----------------------------------------------------------

    async def _do_get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None,
        headers: dict[str, str] | None,
    ) -> dict[str, Any]:
        assert self._client is not None

        merged_headers = self._request_headers(extra=headers)

        async with self._limiter:
            response = await self._client.get(url, params=params, headers=merged_headers)

        if response.status_code == 429:
            logger.warning("Rate limited by Kaspi at {}", url)
            raise RateLimitedError("Kaspi returned 429", status=429, url=url)

        if response.status_code in _RETRY_STATUSES:
            raise KaspiApiError(
                f"Transient {response.status_code} on {url}",
                status=response.status_code,
                url=url,
            )

        if response.status_code >= 400:
            raise KaspiApiError(
                f"HTTP {response.status_code} on {url}",
                status=response.status_code,
                url=url,
            )

        try:
            return orjson.loads(response.content)
        except orjson.JSONDecodeError as e:
            raise KaspiApiError(f"Invalid JSON from {url}: {e}", url=url) from e

    def _base_headers(self) -> dict[str, str]:
        """Headers that don't change per request."""
        return {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ru-RU,ru;q=0.9,kk-KZ;q=0.8,kk;q=0.7,en;q=0.6",
            "Accept-Encoding": "gzip, deflate, br",
            "Cache-Control": "no-cache",
            "Origin": self._settings.base_url,
            "Referer": f"{self._settings.base_url}/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }

    def _request_headers(self, *, extra: dict[str, str] | None) -> dict[str, str]:
        """Per-request headers: rotating UA + caller overrides."""
        headers = {"User-Agent": random.choice(self._settings.user_agents)}
        if extra:
            headers.update(extra)
        return headers
