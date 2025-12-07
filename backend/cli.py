#!/usr/bin/env python3
"""
ABVTrends CLI

Command-line interface for running scrapers and maintenance tasks.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add backend directory to path
sys.path.insert(0, str(Path(__file__).parent))

import click
from rich.console import Console
from rich.table import Table

from app.services.scraper_orchestrator import ScraperOrchestrator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

console = Console()


@click.group()
def cli():
    """ABVTrends CLI - Manage scrapers and data processing"""
    pass


@cli.command()
@click.option(
    "--tier1/--no-tier1",
    default=True,
    help="Run tier1 (media) scrapers",
)
@click.option(
    "--tier2/--no-tier2",
    default=True,
    help="Run tier2 (retailer) scrapers",
)
@click.option(
    "--parallel/--sequential",
    default=False,
    help="Run scrapers in parallel (faster but more intensive)",
)
def scrape(tier1: bool, tier2: bool, parallel: bool):
    """Run scrapers to collect fresh data"""
    console.print("[bold blue]ABVTrends Scraper[/bold blue]")
    console.print("=" * 60)

    if not tier1 and not tier2:
        console.print("[red]Error: Must enable at least tier1 or tier2[/red]")
        return

    mode = "parallel" if parallel else "sequential"
    console.print(f"Mode: {mode}")
    console.print(f"Tier1 (media): {'✓' if tier1 else '✗'}")
    console.print(f"Tier2 (retailer): {'✓' if tier2 else '✗'}")
    console.print()

    async def run_scrapers():
        orchestrator = ScraperOrchestrator()

        with console.status("[bold green]Running scrapers...") as status:
            summary = await orchestrator.run_all_scrapers(
                include_tier1=tier1,
                include_tier2=tier2,
                parallel=parallel,
            )

        # Display results
        console.print()
        console.print("[bold green]✓ Scraping Complete[/bold green]")
        console.print()

        # Create summary table
        table = Table(title="Scraping Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta")

        table.add_row("Duration", f"{summary['duration_seconds']:.2f}s")
        table.add_row("Scrapers Run", str(summary['scrapers_run']))
        table.add_row("Scrapers Failed", str(summary['scrapers_failed']))
        table.add_row("Items Collected", str(summary['items_collected']))
        table.add_row("Items Stored", str(summary['items_stored']))

        console.print(table)

        if summary['errors']:
            console.print()
            console.print("[bold red]Errors:[/bold red]")
            for name, error in summary['errors'].items():
                console.print(f"  • {name}: {error}")

    asyncio.run(run_scrapers())


@cli.command()
@click.argument("scraper_name")
def scrape_one(scraper_name: str):
    """Run a single scraper by name"""
    console.print(f"[bold blue]Running scraper: {scraper_name}[/bold blue]")

    async def run_single():
        orchestrator = ScraperOrchestrator()

        try:
            result = await orchestrator.run_single_scraper(scraper_name)

            if result.get("error"):
                console.print(f"[red]✗ Error: {result['error']}[/red]")
            else:
                console.print()
                console.print("[bold green]✓ Complete[/bold green]")
                console.print(f"Items collected: {result['items_collected']}")
                console.print(f"Items stored: {result['items_stored']}")
                console.print(f"Duration: {result['duration_seconds']:.2f}s")

        except ValueError as e:
            console.print(f"[red]Error: {e}[/red]")
            console.print()
            console.print("Available scrapers:")
            for name in sorted(
                list(ScraperOrchestrator.TIER1_SCRAPERS.keys())
                + list(ScraperOrchestrator.TIER2_SCRAPERS.keys())
            ):
                console.print(f"  • {name}")

    asyncio.run(run_single())


@cli.command()
def list_scrapers():
    """List all available AI-powered scraper sources"""
    from app.scrapers.sources_config import TIER1_MEDIA_SOURCES, TIER2_RETAIL_SOURCES

    console.print("[bold blue]Available AI Scraper Sources[/bold blue]")
    console.print()

    console.print("[bold cyan]Tier 1 (Media) - 20 sources[/bold cyan]")
    for source in sorted(TIER1_MEDIA_SOURCES, key=lambda x: x["name"]):
        console.print(f"  • {source['name']} (priority: {source['priority']})")

    console.print()
    console.print("[bold cyan]Tier 2 (Retailers) - 12 sources[/bold cyan]")
    for source in sorted(TIER2_RETAIL_SOURCES, key=lambda x: x["name"]):
        console.print(f"  • {source['name']} (priority: {source['priority']})")

    console.print()
    console.print(f"[bold green]Total: {len(TIER1_MEDIA_SOURCES) + len(TIER2_RETAIL_SOURCES)} sources[/bold green]")


@cli.command()
def recalculate_trends():
    """Recalculate all trend scores from existing signals"""
    console.print("[bold blue]Recalculating Trend Scores[/bold blue]")

    async def recalc():
        from app.core.database import get_db_context
        from app.services.trend_engine import TrendEngine

        async with get_db_context() as session:
            trend_engine = TrendEngine(session)
            with console.status("[bold green]Calculating..."):
                updated_count = await trend_engine.calculate_all_scores()

            console.print()
            console.print(f"[bold green]✓ Updated {updated_count} products[/bold green]")

    asyncio.run(recalc())


@cli.command()
def init_db():
    """Initialize database tables"""
    console.print("[bold blue]Initializing Database[/bold blue]")

    async def init():
        from app.core.database import init_db

        with console.status("[bold green]Creating tables..."):
            await init_db()

        console.print("[bold green]✓ Database initialized[/bold green]")

    asyncio.run(init())


@cli.command()
@click.option(
    "--source",
    default="BevNET",
    help="Source name to scrape (e.g., 'BevNET', 'VinePair')",
)
@click.option(
    "--max-articles",
    default=5,
    help="Maximum articles to extract",
)
@click.option(
    "--api-key",
    envvar="OPENAI_API_KEY",
    help="OpenAI API key (or set OPENAI_API_KEY env var)",
)
def ai_scrape(source: str, max_articles: int, api_key: str):
    """Test AI-powered scraping on a single source"""
    console.print(f"[bold blue]AI Scraping: {source}[/bold blue]")
    console.print("=" * 60)

    if not api_key:
        console.print(
            "[red]Error: OPENAI_API_KEY environment variable not set[/red]"
        )
        console.print(
            "Set it with: export OPENAI_API_KEY='your-key-here'"
        )
        return

    async def run_ai_scrape():
        from app.scrapers.ai_scraper import AIWebScraper
        from app.scrapers.sources_config import get_source_by_name

        # Get source config
        source_config = get_source_by_name(source)
        if not source_config:
            console.print(f"[red]Error: Unknown source '{source}'[/red]")
            console.print()
            console.print("Available sources:")
            from app.scrapers.sources_config import ALL_SOURCES

            for s in sorted(ALL_SOURCES, key=lambda x: x["name"]):
                console.print(f"  • {s['name']}")
            return

        console.print(f"Source: {source_config['name']}")
        console.print(f"URL: {source_config['url']}")
        console.print(f"Max articles: {max_articles}")
        console.print()

        async with AIWebScraper(openai_api_key=api_key) as scraper:
            with console.status(
                f"[bold green]AI extracting from {source_config['name']}..."
            ):
                items = await scraper.scrape_source(
                    source_config, max_articles=max_articles
                )

            console.print()
            console.print(f"[bold green]✓ Extracted {len(items)} items[/bold green]")
            console.print()

            # Display results
            if items:
                table = Table(title="Extracted Trends")
                table.add_column("Title", style="cyan", no_wrap=False)
                table.add_column("Brand", style="magenta")
                table.add_column("Category", style="green")
                table.add_column("Reason", style="yellow")

                for item in items[:10]:  # Show first 10
                    table.add_row(
                        item.title[:60] + "..." if len(item.title) > 60 else item.title,
                        item.raw_data.get("brand", "N/A"),
                        item.raw_data.get("category", "N/A"),
                        item.raw_data.get("trend_reason", "N/A"),
                    )

                console.print(table)

    asyncio.run(run_ai_scrape())


if __name__ == "__main__":
    cli()
