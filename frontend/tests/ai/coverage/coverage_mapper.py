#!/usr/bin/env python3
"""
CLAUDE-COVERAGE: AI Test Coverage Mapper

Analyzes source code, routes, components, and API endpoints to identify
untested areas and propose additional tests.
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
You are CLAUDE-COVERAGE, an AI testing auditor for the ABVTrends application.

ABVTrends Tech Stack:
- Frontend: Next.js, React, TypeScript, TailwindCSS
- Backend: FastAPI, Python, PostgreSQL
- Testing: Playwright for E2E, API tests

You analyze:
- Source code structure
- Routes and pages
- Components
- API endpoints
- Existing Playwright tests

Your job:
1. Identify untested routes and components
2. Identify missing test types (E2E, API, integration, edge cases)
3. Analyze test coverage gaps
4. Propose additional tests with priority levels
5. Output a detailed markdown report

Coverage Categories:
- Page/Route Coverage: Are all pages tested?
- Component Coverage: Are interactive components tested?
- API Coverage: Are all endpoints tested?
- User Flow Coverage: Are critical user journeys tested?
- Error State Coverage: Are error scenarios tested?
- Edge Case Coverage: Are boundary conditions tested?

Priority Levels:
- P0 (Critical): Core functionality, must be tested
- P1 (High): Important features, should be tested
- P2 (Medium): Nice to have coverage
- P3 (Low): Optional/future coverage
"""


def scan_frontend_pages() -> dict:
    """Scan frontend pages directory."""
    pages_dir = FRONTEND_DIR / "pages"
    pages = {}

    if pages_dir.exists():
        for file in pages_dir.rglob("*.tsx"):
            relative_path = file.relative_to(pages_dir)
            route = "/" + str(relative_path).replace(".tsx", "").replace("index", "").rstrip("/")
            route = route.replace("[", ":").replace("]", "")  # Convert dynamic routes

            try:
                content = file.read_text()
                # Extract data-testid attributes
                testids = re.findall(r'data-testid="([^"]+)"', content)
                # Extract component usage
                components = re.findall(r'<([A-Z][A-Za-z]+)', content)
                pages[route] = {
                    "file": str(file.relative_to(FRONTEND_DIR)),
                    "testids": list(set(testids)),
                    "components": list(set(components))
                }
            except Exception as e:
                pages[route] = {"file": str(file.relative_to(FRONTEND_DIR)), "error": str(e)}

    return pages


def scan_frontend_components() -> dict:
    """Scan frontend components directory."""
    components_dir = FRONTEND_DIR / "components"
    components = {}

    if components_dir.exists():
        for file in components_dir.rglob("*.tsx"):
            name = file.stem
            try:
                content = file.read_text()
                testids = re.findall(r'data-testid="([^"]+)"', content)
                props = re.findall(r'interface\s+\w+Props\s*{([^}]+)}', content)
                components[name] = {
                    "file": str(file.relative_to(FRONTEND_DIR)),
                    "testids": list(set(testids)),
                    "has_props": bool(props)
                }
            except Exception as e:
                components[name] = {"file": str(file.relative_to(FRONTEND_DIR)), "error": str(e)}

    return components


def scan_existing_tests() -> dict:
    """Scan existing Playwright tests."""
    tests_dir = ROOT_DIR.parent / "playwright"
    tests = {"e2e": [], "api": []}

    if tests_dir.exists():
        # E2E tests
        e2e_dir = tests_dir / "e2e"
        if e2e_dir.exists():
            for file in e2e_dir.glob("*.spec.ts"):
                try:
                    content = file.read_text()
                    # Extract test descriptions
                    describes = re.findall(r"test\.describe\(['\"]([^'\"]+)", content)
                    test_cases = re.findall(r"test\(['\"]([^'\"]+)", content)
                    tests["e2e"].append({
                        "file": file.name,
                        "describes": describes,
                        "tests": test_cases
                    })
                except:
                    tests["e2e"].append({"file": file.name, "error": "Could not parse"})

        # API tests
        api_dir = tests_dir / "api"
        if api_dir.exists():
            for file in api_dir.glob("*.spec.ts"):
                try:
                    content = file.read_text()
                    describes = re.findall(r"test\.describe\(['\"]([^'\"]+)", content)
                    test_cases = re.findall(r"test\(['\"]([^'\"]+)", content)
                    tests["api"].append({
                        "file": file.name,
                        "describes": describes,
                        "tests": test_cases
                    })
                except:
                    tests["api"].append({"file": file.name, "error": "Could not parse"})

    return tests


def scan_backend_routes() -> list:
    """Scan backend API routes."""
    backend_dir = FRONTEND_DIR.parent / "backend"
    routes = []

    if backend_dir.exists():
        api_dir = backend_dir / "app" / "api"
        if api_dir.exists():
            for file in api_dir.rglob("*.py"):
                try:
                    content = file.read_text()
                    # Extract FastAPI route decorators
                    get_routes = re.findall(r'@\w+\.get\(["\']([^"\']+)', content)
                    post_routes = re.findall(r'@\w+\.post\(["\']([^"\']+)', content)
                    put_routes = re.findall(r'@\w+\.put\(["\']([^"\']+)', content)
                    delete_routes = re.findall(r'@\w+\.delete\(["\']([^"\']+)', content)

                    for route in get_routes:
                        routes.append({"method": "GET", "path": route, "file": str(file.name)})
                    for route in post_routes:
                        routes.append({"method": "POST", "path": route, "file": str(file.name)})
                    for route in put_routes:
                        routes.append({"method": "PUT", "path": route, "file": str(file.name)})
                    for route in delete_routes:
                        routes.append({"method": "DELETE", "path": route, "file": str(file.name)})
                except:
                    continue

    return routes


def run_coverage_analysis() -> str:
    """Run full coverage analysis with Claude."""

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return "Error: ANTHROPIC_API_KEY not set"

    print("Scanning codebase...")

    # Gather all information
    pages = scan_frontend_pages()
    components = scan_frontend_components()
    tests = scan_existing_tests()
    api_routes = scan_backend_routes()

    print(f"  Found {len(pages)} pages")
    print(f"  Found {len(components)} components")
    print(f"  Found {len(tests['e2e'])} E2E test files")
    print(f"  Found {len(tests['api'])} API test files")
    print(f"  Found {len(api_routes)} backend routes")

    analysis_data = {
        "pages": pages,
        "components": components,
        "existing_tests": tests,
        "api_routes": api_routes
    }

    print("\nSending to Claude for coverage analysis...")

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8000,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"""
## Codebase Analysis

### Frontend Pages
{json.dumps(pages, indent=2)}

### Frontend Components
{json.dumps(components, indent=2)}

### Existing Tests
{json.dumps(tests, indent=2)}

### Backend API Routes
{json.dumps(api_routes, indent=2)}

---

Please analyze this codebase and provide:

1. **Coverage Summary**
   - Overall test coverage assessment
   - Coverage by category (pages, components, API, user flows)

2. **Gap Analysis**
   - Untested pages/routes
   - Untested components
   - Untested API endpoints
   - Missing user flow tests
   - Missing error state tests

3. **Recommendations**
   - Prioritized list of tests to add (P0-P3)
   - Specific test scenarios for each gap
   - Suggested test file structure

4. **Coverage Metrics**
   - Estimated current coverage percentage
   - Target coverage goals

Format as a detailed markdown report.
"""
            }
        ]
    )

    return message.content[0].text


def save_report(report: str):
    """Save the coverage report."""

    results_dir = ROOT_DIR / "results"
    results_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = results_dir / f"coverage_report_{timestamp}.md"

    with open(report_file, "w") as f:
        f.write(f"# ABVTrends Test Coverage Report\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")
        f.write("---\n\n")
        f.write(report)

    print(f"\nCoverage report saved to: {report_file}")

    # Also save to standard location
    standard_report = results_dir / "coverage_report.md"
    with open(standard_report, "w") as f:
        f.write(f"# ABVTrends Test Coverage Report\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")
        f.write("---\n\n")
        f.write(report)


def main():
    """Main execution flow."""

    print("=" * 60)
    print("CLAUDE-COVERAGE: AI Test Coverage Mapper")
    print("=" * 60)

    report = run_coverage_analysis()

    if report.startswith("Error:"):
        print(report)
        return 1

    save_report(report)

    print("\n" + "=" * 60)
    print("Coverage analysis complete!")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
