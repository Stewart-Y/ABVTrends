#!/usr/bin/env python3
"""
CLAUDE-UNITTESTER: AI Unit Test Generator

Generates comprehensive pytest unit tests for backend services and models.
Covers edge cases, error conditions, and expected outputs.
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
BACKEND_TESTS_DIR = BACKEND_DIR / "tests"

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
You are CLAUDE-UNITTESTER, an expert in Python testing with pytest.

Your job:
1. Analyze backend services and models
2. Generate comprehensive pytest unit tests
3. Use async pytest style (pytest-asyncio) when testing async code
4. Cover edge cases, error conditions, and expected outputs
5. Use proper fixtures and mocking

ABVTrends Backend Stack:
- FastAPI with async endpoints
- SQLAlchemy 2.0 with async sessions
- PostgreSQL database
- Pydantic v2 for validation
- pytest + pytest-asyncio for testing

Test Categories to Cover:
1. Happy path tests
2. Edge cases (empty inputs, boundary values)
3. Error handling (invalid inputs, missing data)
4. Database interactions (with mocked sessions)
5. Async behavior

Mocking Guidelines:
- Mock database sessions with AsyncMock
- Mock external API calls
- Use pytest fixtures for reusable test data
- Use parametrize for multiple test cases

Output Format:
Return complete, runnable pytest test files with:
- Proper imports
- Fixtures
- Test functions
- Docstrings explaining each test

Example structure:
```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

# Fixtures
@pytest.fixture
def sample_product():
    return {...}

# Tests
@pytest.mark.asyncio
async def test_function_name():
    '''Test description'''
    ...
```
"""


def scan_backend_modules() -> dict[str, str]:
    """Scan backend for testable modules."""

    modules = {}

    # Services
    services_dir = BACKEND_DIR / "app" / "services"
    if services_dir.exists():
        for file in services_dir.glob("*.py"):
            if not file.name.startswith("_"):
                modules[f"services/{file.name}"] = file.read_text()

    # Models
    models_dir = BACKEND_DIR / "app" / "models"
    if models_dir.exists():
        for file in models_dir.glob("*.py"):
            if not file.name.startswith("_"):
                modules[f"models/{file.name}"] = file.read_text()

    # API routes
    api_dir = BACKEND_DIR / "app" / "api" / "v1"
    if api_dir.exists():
        for file in api_dir.glob("*.py"):
            if not file.name.startswith("_"):
                modules[f"api/{file.name}"] = file.read_text()

    # Core utilities
    core_dir = BACKEND_DIR / "app" / "core"
    if core_dir.exists():
        for file in core_dir.glob("*.py"):
            if not file.name.startswith("_"):
                modules[f"core/{file.name}"] = file.read_text()

    return modules


def generate_tests_for_module(module_path: str, module_content: str) -> str:
    """Generate tests for a single module."""

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return "# Error: ANTHROPIC_API_KEY not set"

    print(f"  Generating tests for: {module_path}")

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8000,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"""
Generate comprehensive pytest unit tests for this Python module.

## Module: {module_path}

```python
{module_content}
```

Requirements:
1. Test all public functions and methods
2. Include happy path and error cases
3. Use proper mocking for database/external calls
4. Add docstrings to all tests
5. Use pytest.mark.asyncio for async tests
6. Include fixtures for common test data

Return the complete test file content only.
"""
            }
        ]
    )

    content = response.content[0].text

    # Extract code block if wrapped in markdown
    code_match = re.search(r'```python\n(.*?)```', content, re.DOTALL)
    if code_match:
        return code_match.group(1)

    return content


def generate_all_tests(target_module: str = None) -> dict[str, str]:
    """Generate tests for all or specific modules."""

    modules = scan_backend_modules()
    generated_tests = {}

    if target_module:
        # Filter to specific module
        modules = {k: v for k, v in modules.items() if target_module in k}

    if not modules:
        print("No modules found to test")
        return {}

    print(f"\nGenerating tests for {len(modules)} module(s)...")

    for module_path, content in modules.items():
        try:
            test_code = generate_tests_for_module(module_path, content)
            generated_tests[module_path] = test_code
        except Exception as e:
            print(f"  Error generating tests for {module_path}: {e}")
            generated_tests[module_path] = f"# Error: {e}"

    return generated_tests


def save_tests(generated_tests: dict[str, str]):
    """Save generated tests to files."""

    BACKEND_TESTS_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    saved_files = []

    for module_path, test_code in generated_tests.items():
        # Create test filename
        module_name = Path(module_path).stem
        category = module_path.split("/")[0]

        # Create category subdirectory
        test_dir = BACKEND_TESTS_DIR / category
        test_dir.mkdir(exist_ok=True)

        test_file = test_dir / f"test_{module_name}.py"

        # Add header
        full_content = f'''#!/usr/bin/env python3
"""
Auto-generated unit tests for {module_path}
Generated: {datetime.now().isoformat()}
"""

{test_code}
'''

        with open(test_file, "w") as f:
            f.write(full_content)

        saved_files.append(str(test_file))
        print(f"  Saved: {test_file}")

    # Save summary
    summary_file = RESULTS_DIR / f"unit_tests_generated_{timestamp}.json"
    with open(summary_file, "w") as f:
        json.dump({
            "timestamp": timestamp,
            "modules_tested": list(generated_tests.keys()),
            "files_created": saved_files
        }, f, indent=2)

    print(f"\nSummary saved to: {summary_file}")

    # Create conftest.py if it doesn't exist
    conftest_file = BACKEND_TESTS_DIR / "conftest.py"
    if not conftest_file.exists():
        conftest_content = '''#!/usr/bin/env python3
"""
Pytest configuration and shared fixtures for ABVTrends backend tests.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.fixture
def sample_product():
    """Sample product data for testing."""
    return {
        "id": "test-uuid-123",
        "name": "Test Whiskey",
        "brand": "Test Brand",
        "category": "spirits",
        "subcategory": "whiskey",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }


@pytest.fixture
def sample_trend():
    """Sample trend data for testing."""
    return {
        "id": "trend-uuid-123",
        "product_id": "test-uuid-123",
        "score": 75.5,
        "trend_tier": "rising",
        "media_score": 80,
        "social_score": 70,
        "retailer_score": 75,
        "price_score": 72,
        "search_score": 78,
        "seasonal_score": 65,
        "signal_count": 25,
        "calculated_at": datetime.utcnow()
    }


@pytest.fixture
def sample_signal():
    """Sample signal data for testing."""
    return {
        "id": "signal-uuid-123",
        "product_id": "test-uuid-123",
        "source": "liquor.com",
        "signal_type": "article_mention",
        "strength": 0.8,
        "captured_at": datetime.utcnow()
    }


@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic client for AI tests."""
    client = MagicMock()
    client.messages.create = MagicMock(return_value=MagicMock(
        content=[MagicMock(text="Mocked AI response")]
    ))
    return client
'''
        with open(conftest_file, "w") as f:
            f.write(conftest_content)
        print(f"  Created: {conftest_file}")

    return saved_files


def main():
    """Main execution flow."""

    print("=" * 60)
    print("CLAUDE-UNITTESTER: AI Unit Test Generator")
    print("=" * 60)

    # Check for specific module argument
    target_module = None
    if len(sys.argv) > 1:
        target_module = sys.argv[1]
        print(f"\nTarget module: {target_module}")

    # Generate tests
    generated_tests = generate_all_tests(target_module)

    if not generated_tests:
        print("No tests generated")
        return 1

    # Save tests
    saved_files = save_tests(generated_tests)

    print("\n" + "=" * 60)
    print("TEST GENERATION COMPLETE")
    print("=" * 60)
    print(f"Generated tests for {len(generated_tests)} module(s)")
    print(f"Files created: {len(saved_files)}")
    print("\nTo run tests:")
    print(f"  cd {BACKEND_DIR}")
    print("  pytest tests/ -v")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
