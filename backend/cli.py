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

# Load .env file
from dotenv import load_dotenv
load_dotenv()

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


@cli.command()
@click.argument("distributor")
@click.option(
    "--category",
    default=None,
    help="Specific category to scrape (e.g., 'Spirits', 'Wine')",
)
@click.option(
    "--limit",
    default=None,
    type=int,
    help="Maximum products to fetch",
)
def scrape_distributor(distributor: str, category: str, limit: int):
    """
    Scrape products from a distributor portal.

    Supported distributors: libdib, sgws, rndc
    """
    import os
    from app.scrapers.distributors import DISTRIBUTOR_SCRAPERS

    console.print(f"[bold blue]Scraping distributor: {distributor}[/bold blue]")
    console.print("=" * 60)

    # Check if distributor is supported
    if distributor not in DISTRIBUTOR_SCRAPERS:
        console.print(f"[red]Unknown distributor: {distributor}[/red]")
        console.print()
        console.print("Supported distributors:")
        for name in DISTRIBUTOR_SCRAPERS.keys():
            console.print(f"  • {name}")
        return

    async def run_scrape():
        from app.core.database import get_db_context
        from app.models.product import Product, ProductCategory

        # Load credentials from environment
        credentials = {}
        if distributor == "libdib":
            credentials = {
                "email": os.getenv("LIBDIB_EMAIL"),
                "password": os.getenv("LIBDIB_PASSWORD"),
                "session_id": os.getenv("LIBDIB_SESSION_ID"),
                "csrf_token": os.getenv("LIBDIB_CSRF_TOKEN"),
                "entity_slug": os.getenv("LIBDIB_ENTITY_SLUG"),
            }
        elif distributor == "sgws":
            credentials = {
                "email": os.getenv("SGWS_EMAIL"),
                "password": os.getenv("SGWS_PASSWORD"),
                "account_id": os.getenv("SGWS_ACCOUNT_ID"),
            }
        elif distributor == "rndc":
            credentials = {
                "email": os.getenv("RNDC_EMAIL"),
                "password": os.getenv("RNDC_PASSWORD"),
                "account_id": os.getenv("RNDC_ACCOUNT_ID"),
            }

        if not credentials.get("email"):
            console.print(f"[red]No credentials found for {distributor}[/red]")
            console.print(f"Set environment variables: {distributor.upper()}_EMAIL, {distributor.upper()}_PASSWORD")
            return

        console.print(f"Using credentials for: {credentials.get('email')}")
        console.print()

        # Initialize scraper
        scraper_class = DISTRIBUTOR_SCRAPERS[distributor]
        scraper = scraper_class(credentials)

        try:
            # Authenticate
            with console.status("[bold green]Authenticating..."):
                authenticated = await scraper.authenticate()

            if not authenticated:
                console.print("[red]✗ Authentication failed[/red]")
                console.print("Try refreshing session tokens or check credentials.")
                return

            console.print("[green]✓ Authenticated successfully[/green]")
            console.print()

            # Get categories
            categories = await scraper.get_categories()
            if category:
                # Filter to specific category
                categories = [c for c in categories if c.get("filter") == category or c.get("name") == category]

            console.print(f"Scraping {len(categories)} categories...")
            console.print()

            all_products = []

            for cat in categories:
                cat_name = cat.get("name") or cat.get("filter") or "all"
                cat_filter = cat.get("filter") or cat.get("id")

                with console.status(f"[bold green]Scraping {cat_name}..."):
                    products = await scraper.get_products(
                        category=cat_filter,
                        limit=limit,
                    )
                    all_products.extend(products)

                console.print(f"  {cat_name}: {len(products)} products")

            console.print()
            console.print(f"[bold]Total products scraped: {len(all_products)}[/bold]")
            console.print()

            # Store products in database
            if all_products:
                with console.status("[bold green]Storing products in database..."):
                    async with get_db_context() as session:
                        stored = 0
                        updated = 0

                        for raw_product in all_products:
                            # Check if product exists
                            from sqlalchemy import select

                            # Try to find by name match
                            stmt = select(Product).where(
                                Product.name == raw_product.name
                            ).limit(1)
                            result = await session.execute(stmt)
                            existing = result.scalar_one_or_none()

                            if existing:
                                # Update existing product
                                if raw_product.image_url:
                                    existing.image_url = raw_product.image_url
                                if raw_product.description:
                                    existing.description = raw_product.description
                                updated += 1
                            else:
                                # Create new product
                                # Map category string to enum
                                cat_enum = ProductCategory.SPIRITS
                                if raw_product.category:
                                    cat_lower = raw_product.category.lower()
                                    if "wine" in cat_lower:
                                        cat_enum = ProductCategory.WINE
                                    elif "beer" in cat_lower:
                                        cat_enum = ProductCategory.BEER
                                    elif "rtd" in cat_lower or "ready" in cat_lower:
                                        cat_enum = ProductCategory.RTD

                                product = Product(
                                    name=raw_product.name,
                                    brand=raw_product.brand,
                                    category=cat_enum,
                                    description=raw_product.description,
                                    image_url=raw_product.image_url,
                                    volume_ml=raw_product.volume_ml,
                                    abv=raw_product.abv,
                                )
                                session.add(product)
                                stored += 1

                        await session.commit()

                console.print(f"[green]✓ Stored {stored} new products, updated {updated} existing[/green]")

        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            import traceback
            traceback.print_exc()

        finally:
            # Close browser for RNDC scraper (has persistent session)
            if hasattr(scraper, 'close'):
                await scraper.close()
            await scraper.session.aclose()

    asyncio.run(run_scrape())


@cli.command()
@click.option(
    "--count",
    default=50,
    help="Number of products to generate signals for",
)
def seed_data(count: int):
    """Generate demo signals and trend scores for testing"""
    console.print("[bold blue]Generating Demo Data[/bold blue]")
    console.print("=" * 60)

    async def generate():
        import random
        from datetime import datetime, timedelta
        from uuid import uuid4

        from sqlalchemy import select, func
        from app.core.database import get_db_context
        from app.models.product import Product
        from app.models.signal import Signal, SignalType
        from app.models.trend_score import TrendScore

        async with get_db_context() as session:
            # Get all active products
            result = await session.execute(
                select(Product)
                .where(Product.is_active == True)
                .limit(count)
            )
            products = list(result.scalars().all())

            if not products:
                console.print("[red]No products found in database.[/red]")
                console.print("Run the LibDib scraper first: ./cli.py scrape-one libdib")
                return

            console.print(f"Found {len(products)} products")
            console.print()

            # Signal generation parameters
            signal_types_weights = [
                (SignalType.MEDIA_MENTION, 25),
                (SignalType.ARTICLE_FEATURE, 10),
                (SignalType.AWARD_MENTION, 5),
                (SignalType.SOCIAL_MENTION, 20),
                (SignalType.NEW_SKU, 15),
                (SignalType.PRICE_DROP, 10),
                (SignalType.PROMOTION, 10),
                (SignalType.BACK_IN_STOCK, 5),
            ]

            total_signals = 0
            now = datetime.utcnow()

            with console.status("[bold green]Generating signals..."):
                for product in products:
                    # Determine product "popularity" (affects signal count)
                    popularity = random.random()  # 0-1

                    if popularity > 0.9:
                        signal_count = random.randint(15, 30)  # Viral products
                    elif popularity > 0.7:
                        signal_count = random.randint(8, 15)   # Trending
                    elif popularity > 0.5:
                        signal_count = random.randint(4, 8)    # Emerging
                    elif popularity > 0.3:
                        signal_count = random.randint(1, 4)    # Stable
                    else:
                        signal_count = random.randint(0, 1)    # Declining

                    for _ in range(signal_count):
                        # Pick random signal type based on weights
                        signal_type = random.choices(
                            [t for t, w in signal_types_weights],
                            weights=[w for t, w in signal_types_weights],
                        )[0]

                        # Generate random capture time within last 7 days
                        days_ago = random.uniform(0, 7)
                        captured_at = now - timedelta(days=days_ago)

                        # Generate sentiment for media signals
                        sentiment = None
                        if signal_type in {SignalType.MEDIA_MENTION, SignalType.ARTICLE_FEATURE, SignalType.AWARD_MENTION}:
                            # Bias towards positive sentiment
                            sentiment = random.gauss(0.3, 0.3)
                            sentiment = max(-1, min(1, sentiment))

                        # Create raw data based on signal type
                        raw_data = {"source": "demo_generator"}
                        if signal_type == SignalType.PRICE_DROP:
                            raw_data["discount_percent"] = random.randint(5, 30)
                        elif signal_type == SignalType.PROMOTION:
                            raw_data["promo_type"] = random.choice(["holiday", "clearance", "bundle"])
                        elif signal_type in {SignalType.MEDIA_MENTION, SignalType.ARTICLE_FEATURE}:
                            raw_data["headline"] = f"Demo mention of {product.name}"

                        signal = Signal(
                            product_id=product.id,
                            signal_type=signal_type,
                            raw_data=raw_data,
                            sentiment_score=sentiment,
                            captured_at=captured_at,
                            processed=False,
                            title=f"Demo {signal_type.value} for {product.name[:30]}",
                        )
                        session.add(signal)
                        total_signals += 1

                await session.commit()

            console.print(f"[green]✓ Created {total_signals} signals[/green]")
            console.print()

            # Now calculate trend scores
            console.print("[bold]Calculating trend scores...[/bold]")

            from app.services.trend_engine import TrendEngine

            trend_engine = TrendEngine(session)
            with console.status("[bold green]Computing scores..."):
                scored_count = await trend_engine.calculate_all_scores()

            console.print(f"[green]✓ Calculated scores for {scored_count} products[/green]")
            console.print()

            # Show summary by tier
            subquery = (
                select(
                    TrendScore.product_id,
                    func.max(TrendScore.calculated_at).label("latest"),
                )
                .group_by(TrendScore.product_id)
                .subquery()
            )

            result = await session.execute(
                select(TrendScore.score)
                .join(
                    subquery,
                    (TrendScore.product_id == subquery.c.product_id)
                    & (TrendScore.calculated_at == subquery.c.latest),
                )
            )
            scores = [row[0] for row in result.all()]

            if scores:
                viral = sum(1 for s in scores if s >= 90)
                trending = sum(1 for s in scores if 70 <= s < 90)
                emerging = sum(1 for s in scores if 50 <= s < 70)
                stable = sum(1 for s in scores if 30 <= s < 50)
                declining = sum(1 for s in scores if s < 30)

                table = Table(title="Tier Distribution")
                table.add_column("Tier", style="cyan")
                table.add_column("Count", style="magenta")
                table.add_column("Percentage", style="green")

                total = len(scores)
                table.add_row("🔥 Viral (90+)", str(viral), f"{viral/total*100:.1f}%")
                table.add_row("📈 Trending (70-89)", str(trending), f"{trending/total*100:.1f}%")
                table.add_row("✨ Emerging (50-69)", str(emerging), f"{emerging/total*100:.1f}%")
                table.add_row("📊 Stable (30-49)", str(stable), f"{stable/total*100:.1f}%")
                table.add_row("📉 Declining (<30)", str(declining), f"{declining/total*100:.1f}%")

                console.print(table)

            console.print()
            console.print("[bold green]✓ Demo data generation complete![/bold green]")
            console.print("Frontend should now show populated trend data.")

    asyncio.run(generate())


if __name__ == "__main__":
    cli()
