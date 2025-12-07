#!/usr/bin/env python3
"""
CLAUDE-SELECTOR-FIXER: AI Selector Auto-Fix Agent

Automatically fixes broken Playwright selectors by analyzing test output
and suggesting robust replacements using data-testid attributes.
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
FRONTEND_DIR = ROOT_DIR.parent.parent
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

# Initialize Anthropic client
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """
You are CLAUDE-SELECTOR-FIXER, an AI agent that fixes broken Playwright selectors.

ABVTrends uses data-testid attributes extensively. The naming conventions are:
- Pages: `{page}-page` (e.g., dashboard-page, trends-page)
- Sections: `{name}-section` (e.g., viral-section, new-arrivals-section)
- Cards: `{type}-card` or `{type}-card-{id}` (e.g., trend-card, stat-card)
- Inputs: `{purpose}-input` (e.g., search-input, category-filter)
- Buttons: `{action}-button` (e.g., start-scraper-button, back-button)
- Loading states: `{component}-loading`
- Empty states: `{component}-empty`
- Tables: `{name}-table`, `{name}-table-header`, `{name}-row-{id}`

Your job:
1. Analyze failing test output and identify broken selectors
2. Determine the root cause (element not found, selector changed, timing issue)
3. Suggest fixed selectors using data-testid attributes where possible
4. Improve selector robustness
5. Add appropriate waits if needed

Output format:
For each broken selector, provide:
1. Original selector
2. Error message
3. Root cause analysis
4. Fixed selector
5. Additional recommendations (waits, assertions, etc.)

Then provide the complete fixed test file code.
"""


def load_test_output() -> str:
    """Load the latest test output or Claude analysis."""

    results_dir = ROOT_DIR / "results"

    # Try to find playwright results
    playwright_results = results_dir / "playwright-results.json"
    if playwright_results.exists():
        try:
            with open(playwright_results) as f:
                data = json.load(f)
            return f"Playwright JSON Results:\n{json.dumps(data, indent=2)}"
        except:
            pass

    # Try to find any analysis file
    analysis_files = list(results_dir.glob("analysis_*.json"))
    if analysis_files:
        latest = max(analysis_files, key=lambda p: p.stat().st_mtime)
        try:
            with open(latest) as f:
                data = json.load(f)
            return f"Previous Analysis:\n{json.dumps(data, indent=2)}"
        except:
            pass

    return "No test output found. Please run tests first."


def load_test_files() -> dict:
    """Load current test file contents."""

    tests_dir = ROOT_DIR.parent / "playwright"
    test_files = {}

    if tests_dir.exists():
        for file in tests_dir.rglob("*.spec.ts"):
            try:
                content = file.read_text()
                test_files[str(file.relative_to(tests_dir))] = content
            except:
                continue

    return test_files


def scan_available_testids() -> list:
    """Scan frontend for available data-testid attributes."""

    testids = set()
    pages_dir = FRONTEND_DIR / "pages"
    components_dir = FRONTEND_DIR / "components"

    for search_dir in [pages_dir, components_dir]:
        if search_dir.exists():
            for file in search_dir.rglob("*.tsx"):
                try:
                    content = file.read_text()
                    found = re.findall(r'data-testid="([^"]+)"', content)
                    testids.update(found)
                except:
                    continue

    return sorted(list(testids))


def fix_selectors(test_output: str, test_files: dict, available_testids: list) -> str:
    """Send to Claude for selector fixing."""

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return "Error: ANTHROPIC_API_KEY not set"

    print("Sending to Claude for selector analysis...")

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8000,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"""
## Test Output / Failures
{test_output}

## Current Test Files
{json.dumps(test_files, indent=2)}

## Available data-testid Attributes in Codebase
{json.dumps(available_testids, indent=2)}

---

Please analyze the test failures and:
1. Identify all broken selectors
2. Determine root causes
3. Provide fixed selectors using available data-testid attributes
4. Output complete fixed test file code where needed

Focus on:
- Using data-testid selectors for reliability
- Adding proper waits for dynamic content
- Handling loading and empty states
- Making selectors more robust
"""
            }
        ]
    )

    return message.content[0].text


def save_fixes(output: str):
    """Save the selector fixes."""

    suggestions_dir = ROOT_DIR / "suggestions"
    suggestions_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save full analysis
    fixes_file = suggestions_dir / f"selector_fixes_{timestamp}.md"
    with open(fixes_file, "w") as f:
        f.write(f"# Selector Fix Suggestions\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")
        f.write("---\n\n")
        f.write(output)

    print(f"\nSelector fixes saved to: {fixes_file}")

    # Extract code blocks and save as separate files
    code_pattern = r'```(?:typescript|ts)\n(.*?)```'
    code_blocks = re.findall(code_pattern, output, re.DOTALL)

    for i, code in enumerate(code_blocks):
        code_file = suggestions_dir / f"fixed_test_{timestamp}_{i+1}.ts"
        with open(code_file, "w") as f:
            f.write(code)
        print(f"Fixed test code saved to: {code_file}")


def apply_fixes(output: str, auto_apply: bool = False):
    """Apply fixes to test files (with confirmation)."""

    # Extract file mappings from output
    file_pattern = r'### File: `([^`]+)`\n```(?:typescript|ts)\n(.*?)```'
    matches = re.findall(file_pattern, output, re.DOTALL)

    if not matches:
        print("No file-specific fixes found to apply.")
        return

    tests_dir = ROOT_DIR.parent / "playwright"

    for filename, code in matches:
        target_file = tests_dir / filename

        print(f"\n{'='*60}")
        print(f"File: {filename}")
        print(f"{'='*60}")

        if not auto_apply:
            print("\nProposed fix:")
            print(code[:500] + "..." if len(code) > 500 else code)

            response = input("\nApply this fix? (y/n): ").lower().strip()
            if response != 'y':
                print("Skipped.")
                continue

        # Apply the fix
        try:
            with open(target_file, "w") as f:
                f.write(code)
            print(f"Applied fix to {filename}")
        except Exception as e:
            print(f"Error applying fix: {e}")


def main():
    """Main execution flow."""

    print("=" * 60)
    print("CLAUDE-SELECTOR-FIXER: AI Selector Auto-Fix Agent")
    print("=" * 60)

    # Parse arguments
    auto_apply = "--auto-apply" in sys.argv

    # Load data
    print("\nLoading test output...")
    test_output = load_test_output()

    print("Loading test files...")
    test_files = load_test_files()
    print(f"  Found {len(test_files)} test files")

    print("Scanning available data-testid attributes...")
    testids = scan_available_testids()
    print(f"  Found {len(testids)} unique testids")

    # Get fixes from Claude
    output = fix_selectors(test_output, test_files, testids)

    if output.startswith("Error:"):
        print(output)
        return 1

    # Save fixes
    save_fixes(output)

    # Optionally apply fixes
    if auto_apply or input("\nWould you like to review and apply fixes? (y/n): ").lower() == 'y':
        apply_fixes(output, auto_apply)

    print("\n" + "=" * 60)
    print("Selector fixing complete!")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
