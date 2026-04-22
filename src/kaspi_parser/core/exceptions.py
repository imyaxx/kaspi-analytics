"""Domain-specific exceptions.

Keeping them in one place lets us catch by category (e.g. `KaspiApiError`)
instead of grepping through the codebase.
"""

from __future__ import annotations


class KaspiError(Exception):
    """Base class for all project-specific errors."""


class KaspiApiError(KaspiError):
    """Raised when Kaspi returns an unexpected response or status."""

    def __init__(self, message: str, *, status: int | None = None, url: str | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.url = url


class RateLimitedError(KaspiApiError):
    """Kaspi rate-limited us (HTTP 429). Upstream retries kick in."""


class ParsingError(KaspiError):
    """A response parsed OK but didn't match our schema."""


class ConfigError(KaspiError):
    """Invalid or missing configuration."""
