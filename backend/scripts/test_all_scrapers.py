#!/usr/bin/env python3
"""
Test All Scrapers - Local Test Run

Run all 7 distributor scrapers to scrape 10 items each with Discord notifications.

Usage:
    python scripts/test_all_scrapers.py
    python scripts/test_all_scrapers.py --items 5
    python scripts/test_all_scrapers.py --distributors libdib provi
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.stealth_scraper import run_test_scrape, DISTRIBUTOR_SLUGS


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


async def main():
    parser = argparse.ArgumentParser(
        description="Run test scrape for all distributors with Discord notifications"
    )
    parser.add_argument(
        "--items",
        type=int,
        default=10,
        help="Number of items to scrape per distributor (default: 10)",
    )
    parser.add_argument(
        "--distributors",
        nargs="+",
        choices=DISTRIBUTOR_SLUGS,
        help=f"Specific distributors to test (default: all). Options: {', '.join(DISTRIBUTOR_SLUGS)}",
    )

    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("ABVTrends - Test All Scrapers")
    print("=" * 60)
    print(f"Items per distributor: {args.items}")
    print(f"Distributors: {args.distributors or 'ALL'}")
    print("=" * 60 + "\n")

    result = await run_test_scrape(
        items_per_distributor=args.items,
        distributors=args.distributors,
    )

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    for slug, data in result["results"].items():
        status = "✅" if data["success"] else "❌"
        if data["success"]:
            print(f"{status} {slug.upper()}: {data['products']} products")
        else:
            print(f"{status} {slug.upper()}: FAILED - {data['error']}")

    print("=" * 60)
    print(f"Total: {result['total_scraped']} products")
    print(f"Success: {result['successful_count']}/{len(result['results'])} distributors")
    print(f"Duration: {result['duration_seconds']:.0f}s")
    print("=" * 60)

    return result


if __name__ == "__main__":
    asyncio.run(main())
