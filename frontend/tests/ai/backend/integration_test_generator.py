#!/usr/bin/env python3
"""
CLAUDE-INTEGRATION-TESTER: AI Integration Test Generator

Generates FastAPI integration tests using httpx AsyncClient.
Tests full API endpoints with database interactions.
"""

import os
import sys
import re
import json
from datetime import datetime
from pathlib import Path

# Setup paths
SCRIPT_DIR = Path(__file__).parent
ROOT_DIR = SCRIPT_DIR.parent
BACKEND_DIR = ROOT_DIR.parent.parent.parent / "backend"
RESULTS_DIR = ROOT_DIR / "results"
BACKEND_TESTS_DIR = BACKEND_DIR / "tests" / "integration"

# Load .env file
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

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """
You are CLAUDE-INTEGRATION-TESTER, an expert in FastAPI integration testing.

Generate full FastAPI integration tests using httpx AsyncClient.

ABVTrends API Endpoints:
- /api/v1/trends - Trend data and scoring
- /api/v1/products - Product catalog
- /api/v1/forecasts - AI predictions
- /api/v1/signals - Trend signals
- /api/v1/scraper - Web scraping controls
- /health - Health check

Test Structure:
```python
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.mark.asyncio
async def test_endpoint(client):
    response = await client.get("/api/v1/endpoint")
    assert response.status_code == 200
```

Test Categories:
1. GET endpoints - verify response structure
2. POST endpoints - verify creation
3. PUT/PATCH endpoints - verify updates
4. DELETE endpoints - verify deletion
5. Query parameters - pagination, filters
6. Error responses - 400, 404, 422, 500
7. Authentication (if applicable)

Include:
- Proper assertions for status codes
- Response body validation
- Edge cases and error scenarios
- Setup/teardown for test data

Output complete, runnable test files only.
"""


def read_api_routes() -> dict[str, str]:
    """Read all API route files."""

    routes = {}
    api_dir = BACKEND_DIR / "app" / "api" / "v1"

    if api_dir.exists():
        for file in api_dir.glob("*.py"):
            if not file.name.startswith("_"):
                routes[file.name] = file.read_text()

    # Also read main.py for app configuration
    main_file = BACKEND_DIR / "app" / "main.py"
    if main_file.exists():
        routes["main.py"] = main_file.read_text()

    return routes


def extract_endpoints(route_content: str) -> list[dict]:
    """Extract endpoint information from route file."""

    endpoints = []

    # Match FastAPI decorators
    patterns = [
        (r'@\w+\.get\(["\']([^"\']+)["\']', "GET"),
        (r'@\w+\.post\(["\']([^"\']+)["\']', "POST"),
        (r'@\w+\.put\(["\']([^"\']+)["\']', "PUT"),
        (r'@\w+\.patch\(["\']([^"\']+)["\']', "PATCH"),
        (r'@\w+\.delete\(["\']([^"\']+)["\']', "DELETE"),
    ]

    for pattern, method in patterns:
        matches = re.findall(pattern, route_content)
        for path in matches:
            endpoints.append({"method": method, "path": path})

    return endpoints


def generate_integration_tests(route_file: str, route_content: str) -> str:
    """Generate integration tests for a route file."""

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return "# Error: ANTHROPIC_API_KEY not set"

    print(f"  Generating integration tests for: {route_file}")

    # Extract endpoint info
    endpoints = extract_endpoints(route_content)

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8000,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"""
Generate comprehensive FastAPI integration tests for this API module.

## Module: {route_file}

```python
{route_content}
```

## Detected Endpoints:
{json.dumps(endpoints, indent=2)}

Requirements:
1. Use httpx AsyncClient with ASGITransport
2. Test all endpoints (GET, POST, PUT, DELETE)
3. Include success and error cases
4. Test query parameters and pagination
5. Validate response structure
6. Add proper docstrings

Return complete test file content only.
"""
            }
        ]
    )

    content = response.content[0].text

    # Extract code block if wrapped
    code_match = re.search(r'```python\n(.*?)```', content, re.DOTALL)
    if code_match:
        return code_match.group(1)

    return content


def generate_all_integration_tests() -> dict[str, str]:
    """Generate integration tests for all API routes."""

    routes = read_api_routes()
    generated_tests = {}

    if not routes:
        print("No API routes found")
        return {}

    print(f"\nGenerating integration tests for {len(routes)} route file(s)...")

    for route_file, content in routes.items():
        if route_file == "main.py":
            continue  # Skip main.py

        try:
            test_code = generate_integration_tests(route_file, content)
            generated_tests[route_file] = test_code
        except Exception as e:
            print(f"  Error: {e}")
            generated_tests[route_file] = f"# Error: {e}"

    return generated_tests


def save_tests(generated_tests: dict[str, str]):
    """Save generated integration tests."""

    BACKEND_TESTS_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    saved_files = []

    for route_file, test_code in generated_tests.items():
        module_name = Path(route_file).stem
        test_file = BACKEND_TESTS_DIR / f"test_api_{module_name}.py"

        full_content = f'''#!/usr/bin/env python3
"""
Auto-generated integration tests for {route_file}
Generated: {datetime.now().isoformat()}

Run with: pytest {test_file.name} -v
"""

{test_code}
'''

        with open(test_file, "w") as f:
            f.write(full_content)

        saved_files.append(str(test_file))
        print(f"  Saved: {test_file}")

    # Create integration test conftest
    conftest_file = BACKEND_TESTS_DIR / "conftest.py"
    conftest_content = '''#!/usr/bin/env python3
"""
Pytest configuration for integration tests.
"""

import pytest
from httpx import AsyncClient, ASGITransport
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.main import app


@pytest.fixture
async def client():
    """Async HTTP client for testing FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def authenticated_client():
    """Authenticated async HTTP client (if auth is implemented)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": "Bearer test-token"}
    ) as ac:
        yield ac


@pytest.fixture
def sample_product_data():
    """Sample product data for POST requests."""
    return {
        "name": "Test Whiskey",
        "brand": "Test Brand",
        "category": "spirits",
        "subcategory": "whiskey"
    }


@pytest.fixture
def sample_trend_data():
    """Sample trend data for POST requests."""
    return {
        "product_id": "test-product-id",
        "score": 75.5,
        "trend_tier": "rising"
    }
'''

    with open(conftest_file, "w") as f:
        f.write(conftest_content)
    print(f"  Created: {conftest_file}")

    # Save summary
    summary_file = RESULTS_DIR / f"integration_tests_generated_{timestamp}.json"
    with open(summary_file, "w") as f:
        json.dump({
            "timestamp": timestamp,
            "routes_tested": list(generated_tests.keys()),
            "files_created": saved_files
        }, f, indent=2)

    return saved_files


def main():
    """Main execution flow."""

    print("=" * 60)
    print("CLAUDE-INTEGRATION-TESTER: FastAPI Integration Test Generator")
    print("=" * 60)

    # Generate tests
    generated_tests = generate_all_integration_tests()

    if not generated_tests:
        print("No tests generated")
        return 1

    # Save tests
    saved_files = save_tests(generated_tests)

    print("\n" + "=" * 60)
    print("INTEGRATION TEST GENERATION COMPLETE")
    print("=" * 60)
    print(f"Generated tests for {len(generated_tests)} route file(s)")
    print(f"Files created: {len(saved_files)}")
    print("\nTo run tests:")
    print(f"  cd {BACKEND_DIR}")
    print("  pytest tests/integration/ -v")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
