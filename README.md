# Kaspi Analytics

Async parser + analytics engine for Kaspi.kz. Crawls Kaspi's internal JSON API
at a polite-but-fast pace, filters out "dead" SKUs, and stores popular products
with full price history in PostgreSQL + TimescaleDB.

## Features

- **Zero hardcode** — every knob (categories, rate limits, thresholds) lives in
  `config.yaml`, validated by Pydantic on startup.
- **Fast by design** — `httpx` async + HTTP/2, rate limiting via `aiolimiter`,
  bulk upserts via `INSERT ... ON CONFLICT`, `orjson` for JSON parsing.
- **Time-series native** — price/stock/rating history in a TimescaleDB
  hypertable; queries like "price trajectory of product X over 90 days" stay
  fast as data grows.
- **Only popular products** — configurable minimum reviews/rating/in-stock
  filter keeps the DB focused on SKUs worth tracking.
- **Observable** — every run records an audit row in `parse_jobs`; loguru +
  rich give human-friendly console output and rotating log files.

## Tech stack

| Layer          | Choice                                           |
| -------------- | ------------------------------------------------ |
| Language       | Python 3.12                                      |
| Package mgr    | uv (fast) or pip                                 |
| HTTP           | httpx (HTTP/2) + aiolimiter + tenacity           |
| Parsing        | Pydantic v2 + orjson                             |
| DB             | PostgreSQL 16 + TimescaleDB                      |
| ORM / migrate  | SQLAlchemy 2 (async) + asyncpg + Alembic         |
| CLI            | Typer + Rich                                     |
| Logging        | Loguru                                           |

## Project layout

```
kaspi-analytics/
├── config.yaml                 # All runtime configuration
├── docker-compose.yml          # Postgres + TimescaleDB + pgAdmin
├── pyproject.toml              # Dependencies (uv-compatible)
├── alembic/                    # Database migrations
│   └── versions/0001_initial.py
└── src/kaspi_parser/
    ├── config.py               # Pydantic Settings (env substitution)
    ├── main.py                 # CLI entrypoint (typer)
    ├── core/
    │   ├── http_client.py      # Async HTTP with rate limit + retry
    │   └── exceptions.py
    ├── api/
    │   ├── endpoints.py        # Kaspi URL builders
    │   ├── schemas.py          # Pydantic models for Kaspi responses
    │   └── client.py           # High-level Kaspi client
    ├── parsers/
    │   ├── category_tree.py    # Resolve whitelist → crawl targets
    │   └── products.py         # Parallel paginated product crawl
    ├── filters/
    │   └── popularity.py       # Popularity threshold filter
    ├── db/
    │   ├── models.py           # SQLAlchemy models
    │   ├── repository.py       # Bulk upserts
    │   └── session.py          # Async engine + session factory
    └── utils/
        └── logger.py           # Loguru setup
```

## Quick start

### 1. Clone & configure

```bash
cp .env.example .env
# Edit .env if you want non-default DB credentials
```

### 2. Start the database

```bash
docker compose up -d postgres
# Wait ~5 seconds for the healthcheck to pass.
docker compose ps
```

Optional pgAdmin UI on `http://localhost:5050`:

```bash
docker compose --profile tools up -d pgadmin
```

### 3. Install Python dependencies

With **uv** (recommended):

```bash
uv sync
```

Or with classic pip:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 4. Run migrations

```bash
alembic upgrade head
```

### 5. Sanity check

```bash
kaspi doctor
```

Expected:

```
✓ Database reachable
✓ Kaspi reachable — 'Одежда — Женщинам' returned 1,234,567 products
```

### 6. Explore the category tree

```bash
kaspi tree
```

Shows exactly which leaf categories will be crawled and how many products each
contains — great for tuning `config.yaml` before committing to a full run.

### 7. Run the parser

```bash
kaspi parse
```

Watch the logs; at the end you get a summary table:

```
                 Parse report
┏━━━━━━━━━━━━━━━━━━━┳━━━━━━┳━━━━━━━┳━━━━━━━┳━━━━━━━━┓
┃ Category          ┃ Seen ┃ Saved ┃ Pages ┃ Errors ┃
┡━━━━━━━━━━━━━━━━━━━╇━━━━━━╇━━━━━━━╇━━━━━━━╇━━━━━━━━┩
│ Платья            │ 4988 │  1842 │   416 │      0 │
│ Джинсы мужские    │ 3204 │  1127 │   267 │      0 │
│ ...               │      │       │       │        │
├───────────────────┼──────┼───────┼───────┼────────┤
│ TOTAL             │ 82k  │  24k  │       │      0 │
└───────────────────┴──────┴───────┴───────┴────────┘
```

## Configuration reference

Everything in `config.yaml`:

| Section       | What it controls                                        |
| ------------- | ------------------------------------------------------- |
| `city`        | Target Kaspi city id (Almaty = 750000000)              |
| `categories`  | Whitelist of categories to crawl; `nested: true` walks entire subtrees |
| `popularity`  | Thresholds for what counts as a "popular" product       |
| `http`        | Rate limit, concurrency, retries, user agents           |
| `pagination`  | Page size, max pages per query, empty-page stop         |
| `database`    | DSN parts (env vars supported via `${VAR:default}`)     |
| `logging`     | Log level, file path, rotation/retention                |

### Adding a new category

Find the category code from Kaspi's tree (visible via `kaspi tree` or in the
raw `treeCategory` JSON), then add:

```yaml
categories:
  whitelist:
    - code: "Smartphones"
      title: "Смартфоны"
      nested: false   # set true to crawl the full subtree
```

## Database schema

- **categories** — flat view of Kaspi's taxonomy (code, parent_code, counts).
- **products** — one row per configSku; stable identity with last-seen stamp.
- **product_snapshots** — TimescaleDB hypertable; one row per (product, time).
  Stores price/discount/rating/reviews/stock/best_merchant + full raw JSON.
- **parse_jobs** — audit log of every parse run.

Useful queries:

```sql
-- 10 fastest-moving SKUs by review growth in the last 7 days
SELECT product_id,
       max(reviews_quantity) - min(reviews_quantity) AS delta
FROM product_snapshots
WHERE captured_at > now() - interval '7 days'
GROUP BY product_id
ORDER BY delta DESC
LIMIT 10;

-- Price trajectory for a single product
SELECT captured_at, unit_sale_price
FROM product_snapshots
WHERE product_id = '106185651'
ORDER BY captured_at;
```

## Development

```bash
ruff check src
ruff format src
mypy src
pytest
```

## Roadmap

- [ ] Dashboard (Next.js + shadcn/ui) reading from `product_snapshots`
- [ ] Autopricing module using Kaspi Merchant API with configurable floor price
- [ ] Competitor deep-scan via `/yml/offer-view/offers/{sku}` for top-N SKUs
- [ ] Scheduled runs via systemd timer or Docker cron

## License

Private / internal use.
