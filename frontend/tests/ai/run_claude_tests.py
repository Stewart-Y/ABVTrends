#!/usr/bin/env python3
"""
ABVTrends AI-Powered Test Runner

Uses Claude API to analyze Playwright test failures and suggest self-healing fixes.
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Load .env file if it exists
SCRIPT_DIR = Path(__file__).parent
env_file = SCRIPT_DIR / ".env"
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

# Configuration
FRONTEND_DIR = SCRIPT_DIR.parent.parent
RESULTS_DIR = SCRIPT_DIR / "results"
SUGGESTIONS_DIR = SCRIPT_DIR / "suggestions"
PROMPTS_DIR = SCRIPT_DIR / "prompts"
PLAYWRIGHT_RESULTS = RESULTS_DIR / "playwright-results.json"

# Claude model
CLAUDE_MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 4096


def ensure_dirs():
    """Create necessary directories."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    SUGGESTIONS_DIR.mkdir(parents=True, exist_ok=True)


def load_system_prompt() -> str:
    """Load the Claude QA system prompt."""
    prompt_file = PROMPTS_DIR / "claude_qa_system_prompt.txt"
    if prompt_file.exists():
        return prompt_file.read_text()
    return "You are a QA automation expert. Analyze test failures and suggest fixes."


def run_playwright_tests() -> tuple[bool, str]:
    """Run Playwright tests and capture results."""
    print("Running Playwright tests...")

    result = subprocess.run(
        ["npm", "run", "test:e2e"],
        cwd=FRONTEND_DIR,
        capture_output=True,
        text=True
    )

    success = result.returncode == 0
    output = result.stdout + "\n" + result.stderr

    return success, output


def load_test_results() -> Optional[dict]:
    """Load Playwright JSON results."""
    if not PLAYWRIGHT_RESULTS.exists():
        print(f"No results file found at {PLAYWRIGHT_RESULTS}")
        return None

    try:
        with open(PLAYWRIGHT_RESULTS) as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"Failed to parse results: {e}")
        return None


def extract_failures(results: dict) -> list[dict]:
    """Extract failed tests from Playwright results."""
    failures = []

    def process_suite(suite, parent_file=None):
        """Recursively process suites (they can be nested)."""
        file = suite.get("file") or parent_file or "unknown"

        # Process specs in this suite
        for spec in suite.get("specs", []):
            for test in spec.get("tests", []):
                for result in test.get("results", []):
                    if result.get("status") not in ("passed", "skipped"):
                        failures.append({
                            "file": file,
                            "title": spec.get("title", "unknown"),
                            "test_title": test.get("title", "unknown"),
                            "status": result.get("status"),
                            "error": result.get("error", {}).get("message", ""),
                            "stack": result.get("error", {}).get("stack", ""),
                            "duration": result.get("duration", 0),
                            "retry": result.get("retry", 0),
                            "attachments": result.get("attachments", [])
                        })

        # Process nested suites
        for nested_suite in suite.get("suites", []):
            process_suite(nested_suite, file)

    for suite in results.get("suites", []):
        process_suite(suite)

    return failures


def analyze_with_claude(failures: list[dict]) -> Optional[dict]:
    """Send failures to Claude for analysis."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY environment variable not set")
        return None

    client = Anthropic(api_key=api_key)
    system_prompt = load_system_prompt()

    user_message = f"""
Analyze the following Playwright test failures and provide self-healing suggestions.

## Test Failures

```json
{json.dumps(failures, indent=2)}
```

For each failure:
1. Identify the root cause
2. Suggest a specific code fix
3. Provide the confidence level (0-1)
4. Note if manual review is required

Respond with a JSON array of analysis objects.
"""

    print(f"Analyzing {len(failures)} failure(s) with Claude...")

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_message}
            ]
        )

        # Extract content from response
        content = response.content[0].text

        # Try to parse as JSON
        try:
            # Find JSON in response (may be wrapped in markdown)
            import re
            json_match = re.search(r'\[[\s\S]*\]', content)
            if json_match:
                return json.loads(json_match.group())
            return {"raw_response": content}
        except json.JSONDecodeError:
            return {"raw_response": content}

    except Exception as e:
        print(f"Claude API error: {e}")
        return None


def save_suggestions(analysis: dict, failures: list[dict]):
    """Save analysis results to file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = SUGGESTIONS_DIR / f"analysis_{timestamp}.json"

    report = {
        "timestamp": timestamp,
        "failures_count": len(failures),
        "failures": failures,
        "analysis": analysis
    }

    with open(output_file, "w") as f:
        json.dump(report, f, indent=2)

    print(f"Analysis saved to: {output_file}")
    return output_file


def apply_suggestions(analysis: dict, auto_apply: bool = False):
    """Apply suggested fixes (with confirmation)."""
    if not isinstance(analysis, list):
        print("Cannot apply suggestions: analysis is not a list")
        return

    for suggestion in analysis:
        if not isinstance(suggestion, dict):
            continue

        fix = suggestion.get("suggested_fix", {})
        if not fix:
            continue

        file_path = fix.get("file")
        original = fix.get("original_code")
        fixed = fix.get("fixed_code")

        if not all([file_path, original, fixed]):
            continue

        print(f"\n{'='*60}")
        print(f"File: {file_path}")
        print(f"Confidence: {suggestion.get('confidence', 'unknown')}")
        print(f"\nOriginal:\n{original}")
        print(f"\nFixed:\n{fixed}")
        print(f"\nExplanation: {fix.get('explanation', 'N/A')}")

        if auto_apply or input("\nApply this fix? (y/n): ").lower() == 'y':
            full_path = FRONTEND_DIR / file_path
            if full_path.exists():
                content = full_path.read_text()
                if original in content:
                    content = content.replace(original, fixed, 1)
                    full_path.write_text(content)
                    print(f"Applied fix to {file_path}")
                else:
                    print(f"Original code not found in {file_path}")
            else:
                print(f"File not found: {full_path}")


def main():
    """Main execution flow."""
    ensure_dirs()

    # Parse arguments
    auto_apply = "--auto-apply" in sys.argv
    skip_run = "--skip-run" in sys.argv

    # Run tests (unless skipped)
    if not skip_run:
        success, output = run_playwright_tests()
        if success:
            print("All tests passed!")
            return 0
        print("Some tests failed. Analyzing...")

    # Load results
    results = load_test_results()
    if not results:
        print("No test results to analyze")
        return 1

    # Extract failures
    failures = extract_failures(results)
    if not failures:
        print("No failures found in results")
        return 0

    print(f"Found {len(failures)} failure(s)")

    # Analyze with Claude
    analysis = analyze_with_claude(failures)
    if not analysis:
        print("Failed to get Claude analysis")
        return 1

    # Save suggestions
    save_suggestions(analysis, failures)

    # Print summary
    if isinstance(analysis, list):
        high_confidence = [a for a in analysis if a.get("confidence", 0) >= 0.8]
        needs_review = [a for a in analysis if a.get("requires_manual_review", False)]

        print(f"\nAnalysis Summary:")
        print(f"  Total suggestions: {len(analysis)}")
        print(f"  High confidence: {len(high_confidence)}")
        print(f"  Needs manual review: {len(needs_review)}")

    # Optionally apply fixes
    if auto_apply or input("\nWould you like to review and apply fixes? (y/n): ").lower() == 'y':
        apply_suggestions(analysis, auto_apply)

    return 0


if __name__ == "__main__":
    sys.exit(main())
