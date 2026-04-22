"""Command-line entrypoint.

Exposes three verbs:

  kaspi tree     — resolve whitelisted categories and print the subtree counts.
  kaspi parse    — full crawl: resolve → fetch → filter → save.
  kaspi doctor   — quick sanity check (config, DB connectivity, Kaspi reachable).

Wiring lives here; real work lives in the parser classes.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from loguru import logger
from rich.console import Console
from rich.table import Table

from kaspi_parser import __version__
from kaspi_parser.api.client import KaspiClient
from kaspi_parser.config import Settings, load_settings
from kaspi_parser.db import repository as repo
from kaspi_parser.db.session import create_engine, session_factory
from kaspi_parser.parsers.category_tree import CategoryTreeParser
from kaspi_parser.parsers.products import ProductParser
from kaspi_parser.utils.logger import setup_logging

app = typer.Typer(
    help="Kaspi.kz marketplace analytics & autopricing toolkit.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


# ---------------------------------------------------------------------------
# Shared bootstrap
# ---------------------------------------------------------------------------
def _bootstrap(config_path: Path | None) -> Settings:
    settings = load_settings(config_path)
    setup_logging(settings.logging)
    logger.info("Kaspi Analytics v{} starting", __version__)
    logger.info("Config loaded from {}", config_path or "config.yaml (default)")
    return settings


# ---------------------------------------------------------------------------
# kaspi tree
# ---------------------------------------------------------------------------
@app.command(help="Resolve whitelisted categories and show the subtree counts.")
def tree(
    config: Path = typer.Option(None, "--config", "-c", help="Path to config.yaml"),
) -> None:
    settings = _bootstrap(config)
    asyncio.run(_run_tree(settings))


async def _run_tree(settings: Settings) -> None:
    engine = create_engine(settings.database)
    sf = session_factory(engine)

    try:
        async with KaspiClient(settings.http) as client:
            tree_parser = CategoryTreeParser(client, sf, settings)
            targets = await tree_parser.build_targets()
    finally:
        await engine.dispose()

    table = Table(title=f"Crawl targets for {settings.city.name}")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Category", style="cyan")
    table.add_column("Code", style="magenta")
    table.add_column("Products", justify="right", style="green")

    for idx, t in enumerate(targets, start=1):
        table.add_row(str(idx), t.title, t.code, f"{t.total:,}")

    table.add_section()
    table.add_row(
        "",
        f"[bold]Total: {len(targets)} categories[/bold]",
        "",
        f"[bold]{sum(t.total for t in targets):,}[/bold]",
    )
    console.print(table)


# ---------------------------------------------------------------------------
# kaspi parse
# ---------------------------------------------------------------------------
@app.command(help="Run a full parse: resolve categories → fetch → filter → save.")
def parse(
    config: Path = typer.Option(None, "--config", "-c", help="Path to config.yaml"),
) -> None:
    settings = _bootstrap(config)
    asyncio.run(_run_parse(settings))


async def _run_parse(settings: Settings) -> None:
    engine = create_engine(settings.database)
    sf = session_factory(engine)

    try:
        async with KaspiClient(settings.http) as client:
            tree_parser = CategoryTreeParser(client, sf, settings)
            targets = await tree_parser.build_targets()

            if not targets:
                logger.error("No categories resolved — check config.yaml")
                raise typer.Exit(code=1)

            # Open a job record for audit trail.
            async with sf() as session:
                async with session.begin():
                    job_id = await repo.create_parse_job(
                        session, city_id=settings.city.id, categories_planned=len(targets)
                    )

            product_parser = ProductParser(client, sf, settings)
            report = await product_parser.crawl(targets)

            # Finalise job record.
            async with sf() as session:
                async with session.begin():
                    await repo.finish_parse_job(
                        session,
                        job_id,
                        products_seen=report.total_seen,
                        products_saved=report.total_saved,
                        errors=report.total_errors,
                        status="success" if report.total_errors == 0 else "partial",
                    )
    finally:
        await engine.dispose()

    _print_report(report)


def _print_report(report) -> None:  # type: ignore[no-untyped-def]
    table = Table(title="Parse report")
    table.add_column("Category", style="cyan")
    table.add_column("Seen", justify="right")
    table.add_column("Saved", justify="right", style="green")
    table.add_column("Pages", justify="right")
    table.add_column("Errors", justify="right", style="red")

    for s in report.per_category:
        table.add_row(
            s.title,
            f"{s.seen:,}",
            f"{s.saved:,}",
            str(s.pages_fetched),
            str(s.errors),
        )

    table.add_section()
    table.add_row(
        "[bold]TOTAL[/bold]",
        f"[bold]{report.total_seen:,}[/bold]",
        f"[bold green]{report.total_saved:,}[/bold green]",
        "",
        f"[bold red]{report.total_errors}[/bold red]" if report.total_errors else "0",
    )
    console.print(table)

    if report.finished_at and report.started_at:
        duration = (report.finished_at - report.started_at).total_seconds()
        console.print(f"\n[dim]Completed in {duration:.1f}s[/dim]")


# ---------------------------------------------------------------------------
# kaspi doctor
# ---------------------------------------------------------------------------
@app.command(help="Quick sanity check: config + DB + Kaspi reachable.")
def doctor(
    config: Path = typer.Option(None, "--config", "-c", help="Path to config.yaml"),
) -> None:
    settings = _bootstrap(config)
    asyncio.run(_run_doctor(settings))


async def _run_doctor(settings: Settings) -> None:
    ok = True

    # 1. DB connectivity
    engine = create_engine(settings.database)
    try:
        async with engine.connect() as conn:
            await conn.exec_driver_sql("SELECT 1")
        console.print("[green]✓[/green] Database reachable")
    except Exception as e:
        console.print(f"[red]✗[/red] Database error: {e}")
        ok = False
    finally:
        await engine.dispose()

    # 2. Kaspi reachable
    try:
        async with KaspiClient(settings.http) as client:
            # Pick first whitelist entry for the probe.
            entry = settings.categories.whitelist[0]
            resp = await client.fetch_filters(entry.code, city_id=settings.city.id)
            console.print(
                f"[green]✓[/green] Kaspi reachable — '{entry.title}' "
                f"returned {resp.data.total:,} products"
            )
    except Exception as e:
        console.print(f"[red]✗[/red] Kaspi error: {e}")
        ok = False

    if not ok:
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# Entrypoint for `python -m kaspi_parser.main`
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app()
