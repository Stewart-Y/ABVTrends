"""
Manual Cookie Capture Helper

Opens a browser for manual login, then captures and saves session cookies.
Use this when automated login is blocked by CAPTCHA.

Usage:
    python -m app.scrapers.utils.cookie_capture --distributor sgws
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Directory to store captured cookies
COOKIES_DIR = Path(__file__).parent.parent.parent.parent / "data" / "cookies"


async def capture_cookies_manual(
    distributor: str,
    login_url: str,
    success_indicator: str = "/search",
    timeout_minutes: int = 5,
) -> Optional[list[dict]]:
    """
    Open a browser for manual login and capture cookies after success.

    Args:
        distributor: Name of the distributor (e.g., 'sgws', 'rndc')
        login_url: URL to the login page
        success_indicator: URL pattern that indicates successful login
        timeout_minutes: How long to wait for manual login

    Returns:
        List of cookies if successful, None if failed/timeout
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error("Playwright not installed")
        return None

    print(f"\n{'='*60}")
    print(f"MANUAL LOGIN REQUIRED - {distributor.upper()}")
    print(f"{'='*60}")
    print(f"\nA browser window will open. Please:")
    print(f"  1. Log in to {distributor.upper()} manually")
    print(f"  2. Solve any CAPTCHA challenges")
    print(f"  3. Complete the login process")
    print(f"\nThe browser will close automatically after successful login.")
    print(f"Timeout: {timeout_minutes} minutes")
    print(f"{'='*60}\n")

    cookies = None

    async with async_playwright() as p:
        # Launch visible browser for manual interaction
        browser = await p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
            ],
        )

        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )

        page = await context.new_page()

        try:
            # Navigate to login page
            await page.goto(login_url, wait_until="domcontentloaded")

            # Wait for user to complete login
            print("Waiting for login completion...")
            timeout_ms = timeout_minutes * 60 * 1000

            try:
                # Wait for URL to contain success indicator
                await page.wait_for_url(
                    f"**{success_indicator}**",
                    timeout=timeout_ms,
                )
                print(f"\n✓ Login successful! URL contains '{success_indicator}'")

            except Exception:
                # Check if we're on a different success page
                current_url = page.url
                if success_indicator not in current_url and "/login" not in current_url:
                    print(f"\n✓ Login appears successful. Current URL: {current_url}")
                else:
                    print(f"\n✗ Timeout waiting for login. Current URL: {current_url}")
                    await browser.close()
                    return None

            # Wait a moment for cookies to settle
            await asyncio.sleep(2)

            # Capture all cookies
            cookies = await context.cookies()
            print(f"Captured {len(cookies)} cookies")

            # Save cookies to file
            COOKIES_DIR.mkdir(parents=True, exist_ok=True)
            cookie_file = COOKIES_DIR / f"{distributor}_cookies.json"

            cookie_data = {
                "distributor": distributor,
                "captured_at": datetime.now().isoformat(),
                "cookies": cookies,
            }

            with open(cookie_file, "w") as f:
                json.dump(cookie_data, f, indent=2)

            print(f"✓ Cookies saved to: {cookie_file}")

        except Exception as e:
            logger.error(f"Error during cookie capture: {e}")

        finally:
            await browser.close()

    return cookies


def load_saved_cookies(distributor: str) -> Optional[list[dict]]:
    """
    Load previously saved cookies for a distributor.

    Args:
        distributor: Name of the distributor

    Returns:
        List of cookies if found, None otherwise
    """
    cookie_file = COOKIES_DIR / f"{distributor}_cookies.json"

    if not cookie_file.exists():
        logger.warning(f"No saved cookies for {distributor}")
        return None

    try:
        with open(cookie_file) as f:
            data = json.load(f)

        captured_at = data.get("captured_at", "unknown")
        cookies = data.get("cookies", [])

        logger.info(f"Loaded {len(cookies)} cookies for {distributor} (captured: {captured_at})")
        return cookies

    except Exception as e:
        logger.error(f"Error loading cookies: {e}")
        return None


def cookies_to_dict(cookies: list[dict]) -> dict[str, str]:
    """Convert Playwright cookie list to simple name->value dict."""
    return {c["name"]: c["value"] for c in cookies}


# Distributor-specific configurations
DISTRIBUTOR_CONFIGS = {
    "sgws": {
        "login_url": "https://shop.sgproof.com/auth/login",
        "success_indicator": "/search",
    },
    "rndc": {
        "login_url": "https://rndc.storenvy.com/login",
        "success_indicator": "/products",
    },
    "breakthru": {
        "login_url": "https://breakthrunow.com/bbg/en/login",
        "success_indicator": "/bbg/en/",
    },
    "sipmarket": {
        "login_url": "https://sipmarket.com/login",
        "success_indicator": "/browse",
    },
    "parkstreet": {
        "login_url": "https://retailer.park-street.com/login",
        "success_indicator": "/dashboard",
    },
}


async def main():
    """CLI entry point for cookie capture."""
    import argparse

    parser = argparse.ArgumentParser(description="Capture cookies via manual login")
    parser.add_argument(
        "--distributor",
        "-d",
        required=True,
        choices=list(DISTRIBUTOR_CONFIGS.keys()),
        help="Distributor to log into",
    )
    parser.add_argument(
        "--timeout",
        "-t",
        type=int,
        default=5,
        help="Timeout in minutes (default: 5)",
    )

    args = parser.parse_args()

    config = DISTRIBUTOR_CONFIGS[args.distributor]

    cookies = await capture_cookies_manual(
        distributor=args.distributor,
        login_url=config["login_url"],
        success_indicator=config["success_indicator"],
        timeout_minutes=args.timeout,
    )

    if cookies:
        print(f"\n✓ Successfully captured {len(cookies)} cookies for {args.distributor}")
        print(f"  These cookies will be automatically used for future scraping sessions.")
    else:
        print(f"\n✗ Failed to capture cookies for {args.distributor}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
