#!/usr/bin/env python3
"""
ABVTrends Unified AI Test Orchestration Script

Runs the complete AI-powered test suite:
1. Playwright E2E tests
2. Claude self-healing analysis
3. Coverage mapping
4. Security scanning
5. Exploratory testing (optional)
"""

import os
import sys
import subprocess
import json
import argparse
from datetime import datetime
from pathlib import Path

# Setup paths
SCRIPT_DIR = Path(__file__).parent
FRONTEND_DIR = SCRIPT_DIR.parent.parent
ROOT_DIR = FRONTEND_DIR.parent
RESULTS_DIR = SCRIPT_DIR / "results"

# Load .env file
env_file = SCRIPT_DIR / ".env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key] = value


def print_header(title: str):
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60 + "\n")


def run_command(cmd: list, cwd: Path = None, check: bool = False) -> tuple[int, str]:
    """Run a command and return exit code and output."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )
        output = result.stdout + "\n" + result.stderr
        return result.returncode, output
    except subprocess.TimeoutExpired:
        return 1, "Command timed out"
    except Exception as e:
        return 1, str(e)


def run_playwright_tests() -> dict:
    """Run Playwright E2E tests."""
    print_header("Running Playwright E2E Tests")

    exit_code, output = run_command(
        ["npm", "run", "test:e2e"],
        cwd=FRONTEND_DIR
    )

    print(output[-2000:] if len(output) > 2000 else output)

    return {
        "name": "Playwright E2E",
        "passed": exit_code == 0,
        "exit_code": exit_code
    }


def run_claude_self_healing() -> dict:
    """Run Claude self-healing analysis on test failures."""
    print_header("Running Claude Self-Healing Analysis")

    script = SCRIPT_DIR / "run_claude_tests.py"
    if not script.exists():
        print("Self-healing script not found")
        return {"name": "Claude Self-Healing", "passed": False, "skipped": True}

    exit_code, output = run_command(
        [sys.executable, str(script), "--skip-run"],
        cwd=SCRIPT_DIR
    )

    print(output[-2000:] if len(output) > 2000 else output)

    return {
        "name": "Claude Self-Healing",
        "passed": exit_code == 0,
        "exit_code": exit_code
    }


def run_coverage_analysis() -> dict:
    """Run AI coverage analysis."""
    print_header("Running AI Coverage Analysis")

    script = SCRIPT_DIR / "coverage" / "coverage_mapper.py"
    if not script.exists():
        print("Coverage mapper not found")
        return {"name": "Coverage Analysis", "passed": False, "skipped": True}

    exit_code, output = run_command(
        [sys.executable, str(script)],
        cwd=SCRIPT_DIR
    )

    print(output[-2000:] if len(output) > 2000 else output)

    return {
        "name": "Coverage Analysis",
        "passed": exit_code == 0,
        "exit_code": exit_code
    }


def run_security_scan() -> dict:
    """Run security scanning with AI analysis."""
    print_header("Running Security Scan")

    script = SCRIPT_DIR / "security" / "security_analyzer.py"
    if not script.exists():
        print("Security analyzer not found")
        return {"name": "Security Scan", "passed": False, "skipped": True}

    exit_code, output = run_command(
        [sys.executable, str(script)],
        cwd=SCRIPT_DIR
    )

    print(output[-2000:] if len(output) > 2000 else output)

    return {
        "name": "Security Scan",
        "passed": exit_code == 0,
        "exit_code": exit_code
    }


def run_exploratory_testing() -> dict:
    """Run AI exploratory testing."""
    print_header("Running AI Exploratory Testing")

    script = SCRIPT_DIR / "explore" / "exploratory_agent.py"
    if not script.exists():
        print("Exploratory agent not found")
        return {"name": "Exploratory Testing", "passed": False, "skipped": True}

    exit_code, output = run_command(
        [sys.executable, str(script)],
        cwd=SCRIPT_DIR
    )

    print(output[-2000:] if len(output) > 2000 else output)

    return {
        "name": "Exploratory Testing",
        "passed": exit_code == 0,
        "exit_code": exit_code
    }


def run_selector_fix() -> dict:
    """Run selector auto-fix agent."""
    print_header("Running Selector Auto-Fix Agent")

    script = SCRIPT_DIR / "selector_fix" / "selector_fix_agent.py"
    if not script.exists():
        print("Selector fix agent not found")
        return {"name": "Selector Fix", "passed": False, "skipped": True}

    exit_code, output = run_command(
        [sys.executable, str(script)],
        cwd=SCRIPT_DIR
    )

    print(output[-2000:] if len(output) > 2000 else output)

    return {
        "name": "Selector Fix",
        "passed": exit_code == 0,
        "exit_code": exit_code
    }


def generate_summary_report(results: list[dict]) -> str:
    """Generate a summary report of all test runs."""

    timestamp = datetime.now().isoformat()

    report = f"""# ABVTrends AI Test Suite Report
Generated: {timestamp}

## Summary

| Test Suite | Status | Exit Code |
|-----------|--------|-----------|
"""

    total_passed = 0
    total_failed = 0

    for result in results:
        if result.get("skipped"):
            status = "⏭️ Skipped"
        elif result["passed"]:
            status = "✅ Passed"
            total_passed += 1
        else:
            status = "❌ Failed"
            total_failed += 1

        exit_code = result.get("exit_code", "N/A")
        report += f"| {result['name']} | {status} | {exit_code} |\n"

    report += f"""
## Overall Result

- **Total Tests:** {len(results)}
- **Passed:** {total_passed}
- **Failed:** {total_failed}
- **Status:** {"✅ ALL PASSED" if total_failed == 0 else "❌ SOME FAILED"}

## Reports Generated

- Playwright HTML Report: `frontend/tests/playwright/reports/index.html`
- Coverage Report: `frontend/tests/ai/results/coverage_report.md`
- Security Report: `frontend/tests/ai/results/security_report.md`
- Exploration Report: `frontend/tests/ai/results/exploration_*.md`
- Self-Healing Suggestions: `frontend/tests/ai/suggestions/`

## Next Steps

"""

    if total_failed > 0:
        report += """1. Review failed test outputs above
2. Check self-healing suggestions in `suggestions/` directory
3. Apply recommended fixes
4. Re-run the test suite
"""
    else:
        report += """1. Review coverage report for gaps
2. Check security report for any concerns
3. Review exploration report for new test ideas
"""

    return report


def main():
    """Main orchestration function."""

    parser = argparse.ArgumentParser(description="ABVTrends AI Test Suite")
    parser.add_argument("--skip-playwright", action="store_true", help="Skip Playwright tests")
    parser.add_argument("--skip-security", action="store_true", help="Skip security scan")
    parser.add_argument("--skip-explore", action="store_true", help="Skip exploratory testing")
    parser.add_argument("--quick", action="store_true", help="Run only essential tests")
    parser.add_argument("--full", action="store_true", help="Run all tests including exploratory")
    args = parser.parse_args()

    print_header("ABVTrends AI Test Suite")
    print(f"Started at: {datetime.now().isoformat()}")
    print(f"Frontend dir: {FRONTEND_DIR}")
    print(f"Results dir: {RESULTS_DIR}")

    # Ensure results directory exists
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    results = []

    # 1. Playwright E2E tests
    if not args.skip_playwright:
        results.append(run_playwright_tests())

    # 2. Claude self-healing (if tests failed)
    if results and not results[-1]["passed"]:
        results.append(run_claude_self_healing())
        results.append(run_selector_fix())

    # 3. Coverage analysis
    if not args.quick:
        results.append(run_coverage_analysis())

    # 4. Security scan
    if not args.skip_security and not args.quick:
        results.append(run_security_scan())

    # 5. Exploratory testing (optional, requires running app)
    if args.full and not args.skip_explore:
        results.append(run_exploratory_testing())

    # Generate summary report
    print_header("Test Suite Summary")
    report = generate_summary_report(results)
    print(report)

    # Save summary report
    report_file = RESULTS_DIR / f"suite_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    with open(report_file, "w") as f:
        f.write(report)
    print(f"\nFull report saved to: {report_file}")

    # Also save as JSON for CI integration
    json_report = {
        "timestamp": datetime.now().isoformat(),
        "results": results,
        "passed": all(r.get("passed", False) or r.get("skipped", False) for r in results)
    }
    json_file = RESULTS_DIR / "suite_report.json"
    with open(json_file, "w") as f:
        json.dump(json_report, f, indent=2)

    # Return appropriate exit code
    failed_count = sum(1 for r in results if not r.get("passed", False) and not r.get("skipped", False))
    return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
