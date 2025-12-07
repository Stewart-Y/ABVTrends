#!/usr/bin/env python3
"""
CLAUDE-EXPLORE: Autonomous Exploratory Testing Agent

Crawls your UI like a human and generates new tests automatically.
"""

import os
import sys
import json
import re
from datetime import datetime
from pathlib import Path

# Load .env file if it exists
SCRIPT_DIR = Path(__file__).parent
ROOT_DIR = SCRIPT_DIR.parent
env_file = ROOT_DIR / ".env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key] = value

try:
    from anthropic import Anthropic
except ImportError:
    print("Error: anthropic package not installed. Run: pip install anthropic")
    sys.exit(1)

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Error: playwright package not installed. Run: pip install playwright && playwright install")
    sys.exit(1)

# Initialize Anthropic client
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """
You are CLAUDE-EXPLORE, an autonomous exploratory testing agent for the ABVTrends application.

ABVTrends is an alcohol trend forecasting platform with:
- Dashboard (/) - KPI cards, tier sections, trend cards
- Trends Explorer (/trends) - filters, search, paginated table
- Discover (/discover) - New Arrivals, Celebrity Bottles, Early Movers sections
- Scraper Panel (/scraper) - AI scraper controls and logs
- Product Detail (/product/[id]) - Score gauge, metrics, charts

Your job:
1. Analyze the exploration results from the headless browser.
2. Identify UI errors, console errors, broken routes.
3. Generate additional Playwright test files that cover all unexplored paths.
4. Use data-testid attributes for selectors (the app uses them extensively).
5. Output test files in TypeScript format compatible with @playwright/test.

Test file format:
- Import from '@playwright/test'
- Import helpers from '../utils/test-helpers'
- Use descriptive test.describe blocks
- Include proper waits and assertions
- Handle loading states and empty states gracefully

Respond with:
1. A markdown exploration report
2. Any new test files needed (with filenames)
"""

def explore_app(base_url: str = "http://localhost:3000") -> tuple[list, list, dict]:
    """Explore the application and gather information."""
    print(f"Starting exploration of {base_url}...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 720})
        page = context.new_page()

        console_errors = []
        console_warnings = []
        network_errors = []

        # Capture console messages
        def handle_console(msg):
            if msg.type == "error":
                console_errors.append(msg.text)
            elif msg.type == "warning":
                console_warnings.append(msg.text)

        page.on("console", handle_console)

        # Capture network failures
        def handle_request_failed(request):
            network_errors.append({
                "url": request.url,
                "method": request.method,
                "failure": request.failure
            })

        page.on("requestfailed", handle_request_failed)

        visited = set()
        page_info = {}

        # Define routes to explore
        routes = ["/", "/trends", "/discover", "/scraper"]

        for route in routes:
            try:
                url = base_url + route
                print(f"  Exploring: {route}")

                page.goto(url, wait_until="networkidle", timeout=30000)

                # Wait for page to stabilize
                page.wait_for_timeout(1000)

                visited.add(route)

                # Gather page information
                page_info[route] = {
                    "title": page.title(),
                    "url": page.url,
                    "links": [],
                    "buttons": [],
                    "forms": [],
                    "data_testids": [],
                    "errors": []
                }

                # Find all links
                links = page.locator("a").all()
                for link in links:
                    try:
                        href = link.get_attribute("href")
                        text = link.inner_text()[:50] if link.inner_text() else ""
                        if href:
                            page_info[route]["links"].append({"href": href, "text": text})
                    except:
                        continue

                # Find all buttons
                buttons = page.locator("button").all()
                for btn in buttons:
                    try:
                        text = btn.inner_text()[:30] if btn.inner_text() else ""
                        testid = btn.get_attribute("data-testid")
                        page_info[route]["buttons"].append({"text": text, "testid": testid})
                    except:
                        continue

                # Find all data-testid elements
                testid_elements = page.locator("[data-testid]").all()
                for elem in testid_elements:
                    try:
                        testid = elem.get_attribute("data-testid")
                        if testid:
                            page_info[route]["data_testids"].append(testid)
                    except:
                        continue

                # Check for visible error states
                error_elements = page.locator("[class*='error'], [class*='Error'], [role='alert']").all()
                for elem in error_elements:
                    try:
                        text = elem.inner_text()[:100]
                        if text:
                            page_info[route]["errors"].append(text)
                    except:
                        continue

            except Exception as e:
                print(f"  Error exploring {route}: {e}")
                page_info[route] = {"error": str(e)}

        # Try to explore product detail page if we can find a product link
        try:
            page.goto(base_url + "/", wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(2000)

            # Look for product links
            product_links = page.locator("a[href*='/product/']").all()
            if product_links:
                first_product = product_links[0]
                href = first_product.get_attribute("href")
                if href:
                    print(f"  Exploring product page: {href}")
                    page.goto(base_url + href if href.startswith("/") else href,
                             wait_until="networkidle", timeout=30000)
                    page.wait_for_timeout(1000)

                    visited.add(href)
                    page_info[href] = {
                        "title": page.title(),
                        "url": page.url,
                        "data_testids": []
                    }

                    testid_elements = page.locator("[data-testid]").all()
                    for elem in testid_elements:
                        try:
                            testid = elem.get_attribute("data-testid")
                            if testid:
                                page_info[href]["data_testids"].append(testid)
                        except:
                            continue
        except Exception as e:
            print(f"  Could not explore product page: {e}")

        browser.close()

    return list(visited), console_errors, {
        "pages": page_info,
        "console_errors": console_errors,
        "console_warnings": console_warnings,
        "network_errors": network_errors
    }


def ask_claude_to_analyze(visited: list, errors: list, exploration_data: dict) -> str:
    """Send exploration results to Claude for analysis and test generation."""

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return "Error: ANTHROPIC_API_KEY not set"

    print("\nSending exploration data to Claude for analysis...")

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8000,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"""
## Exploration Results

### Routes Visited
{json.dumps(visited, indent=2)}

### Console Errors
{json.dumps(errors, indent=2)}

### Detailed Page Information
{json.dumps(exploration_data, indent=2)}

---

Please analyze these results and:
1. Write an exploration report in markdown format
2. Identify any missing test coverage based on the data-testid elements found
3. Suggest or generate any additional Playwright tests needed

Focus on:
- Routes that might not have full test coverage
- Interactive elements that should be tested
- Error scenarios that should be covered
- Edge cases for loading/empty states
"""
            }
        ]
    )

    return message.content[0].text


def save_results(output: str, visited: list, exploration_data: dict):
    """Save exploration results to files."""

    results_dir = ROOT_DIR / "results"
    results_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save exploration report
    report_file = results_dir / f"exploration_{timestamp}.md"
    with open(report_file, "w") as f:
        f.write(f"# ABVTrends Exploration Report\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")
        f.write(f"## Routes Visited\n")
        for route in visited:
            f.write(f"- {route}\n")
        f.write(f"\n---\n\n")
        f.write(output)

    print(f"\nExploration report saved to: {report_file}")

    # Save raw exploration data
    data_file = results_dir / f"exploration_data_{timestamp}.json"
    with open(data_file, "w") as f:
        json.dump(exploration_data, f, indent=2, default=str)

    print(f"Raw exploration data saved to: {data_file}")

    # Extract and save any test files from Claude's output
    test_pattern = r'```(?:typescript|ts)\n(.*?)```'
    test_matches = re.findall(test_pattern, output, re.DOTALL)

    if test_matches:
        suggestions_dir = ROOT_DIR / "suggestions"
        suggestions_dir.mkdir(exist_ok=True)

        for i, test_code in enumerate(test_matches):
            test_file = suggestions_dir / f"suggested_test_{timestamp}_{i+1}.ts"
            with open(test_file, "w") as f:
                f.write(test_code)
            print(f"Suggested test saved to: {test_file}")


def main():
    """Main execution flow."""

    base_url = os.environ.get("BASE_URL", "http://localhost:3000")

    print("=" * 60)
    print("CLAUDE-EXPLORE: Autonomous Exploratory Testing Agent")
    print("=" * 60)

    # Run exploration
    visited, errors, exploration_data = explore_app(base_url)

    print(f"\nExploration complete!")
    print(f"  Routes visited: {len(visited)}")
    print(f"  Console errors found: {len(errors)}")

    # Analyze with Claude
    output = ask_claude_to_analyze(visited, errors, exploration_data)

    # Save results
    save_results(output, visited, exploration_data)

    print("\n" + "=" * 60)
    print("Exploration complete!")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
