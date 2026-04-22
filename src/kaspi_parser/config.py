"""Typed application configuration.

Loads `config.yaml`, substitutes `${ENV_VAR:default}` placeholders from the
environment, and validates the shape with Pydantic. Everything the app reads
at runtime funnels through the `Settings` object returned by `load_settings()`.
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator

# ----------------------------------------------------------------------------
# Env-var substitution: "${VAR:default}" → value from os.environ or default
# ----------------------------------------------------------------------------
_ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)(?::([^}]*))?\}")


def _substitute_env(value: Any) -> Any:
    """Recursively replace `${VAR:default}` placeholders in strings."""
    if isinstance(value, str):
        def repl(match: re.Match[str]) -> str:
            var, default = match.group(1), match.group(2) or ""
            return os.environ.get(var, default)
        return _ENV_PATTERN.sub(repl, value)
    if isinstance(value, dict):
        return {k: _substitute_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute_env(v) for v in value]
    return value


# ----------------------------------------------------------------------------
# Config models
# ----------------------------------------------------------------------------
class CitySettings(BaseModel):
    id: str
    name: str


class CategoryEntry(BaseModel):
    """A category to parse.

    `code` is the Kaspi category code (e.g. "Women's clothing"), which matches
    the suffix of `:category:<code>` used in Kaspi's `q` query parameter.

    When `nested` is True, the parser walks the full subtree; otherwise it
    parses only this exact category (and its leaves if too large).
    """

    code: str
    title: str
    nested: bool = False


class CategoriesSettings(BaseModel):
    whitelist: list[CategoryEntry] = Field(default_factory=list)

    @field_validator("whitelist")
    @classmethod
    def _non_empty(cls, v: list[CategoryEntry]) -> list[CategoryEntry]:
        if not v:
            raise ValueError("categories.whitelist must not be empty")
        return v


class PopularitySettings(BaseModel):
    min_reviews: int = 50
    min_rating: float = 4.0
    require_in_stock: bool = True


class HttpSettings(BaseModel):
    base_url: str = "https://kaspi.kz"
    requests_per_second: float = 6.0
    max_concurrent: int = 8
    timeout_seconds: float = 20.0
    retries: int = 4
    backoff_base: float = 1.5
    backoff_max: float = 60.0
    user_agents: list[str] = Field(default_factory=list)

    @field_validator("user_agents")
    @classmethod
    def _ua_not_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("http.user_agents must contain at least one UA")
        return v


class PaginationSettings(BaseModel):
    page_size: int = 12
    max_pages_per_query: int = 400
    stop_on_empty_pages: int = 2


class DatabaseSettings(BaseModel):
    host: str = "localhost"
    port: int = 5432
    name: str = "kaspi"
    user: str = "kaspi"
    password: str = "kaspi"
    pool_size: int = 20
    max_overflow: int = 10
    echo: bool = False

    @property
    def async_dsn(self) -> str:
        """Async driver DSN for SQLAlchemy."""
        return (
            f"postgresql+asyncpg://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.name}"
        )

    @property
    def sync_dsn(self) -> str:
        """Sync DSN (used by Alembic)."""
        return (
            f"postgresql+psycopg://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.name}"
        )


class LoggingSettings(BaseModel):
    level: str = "INFO"
    file: str = "logs/parser.log"
    rotation: str = "100 MB"
    retention: str = "14 days"


class Settings(BaseModel):
    city: CitySettings
    categories: CategoriesSettings
    popularity: PopularitySettings
    http: HttpSettings
    pagination: PaginationSettings
    database: DatabaseSettings
    logging: LoggingSettings


# ----------------------------------------------------------------------------
# Loader
# ----------------------------------------------------------------------------
DEFAULT_CONFIG_PATH = Path(os.environ.get("CONFIG_PATH", "config.yaml"))


@lru_cache(maxsize=1)
def load_settings(path: Path | None = None) -> Settings:
    """Parse YAML → substitute env vars → validate → cache."""
    config_path = path or DEFAULT_CONFIG_PATH
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    resolved = _substitute_env(raw)
    return Settings.model_validate(resolved)
