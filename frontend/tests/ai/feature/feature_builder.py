#!/usr/bin/env python3
"""
CLAUDE-FEATURE-BUILDER: AI Feature Code Generator

Transforms user stories into production-ready code:
- Backend FastAPI endpoints
- SQLAlchemy models + migrations
- Frontend React/Next.js components
- TypeScript types
- Unit tests + E2E tests
- API documentation
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
PROJECT_ROOT = ROOT_DIR.parent.parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
FRONTEND_DIR = PROJECT_ROOT / "frontend"
RESULTS_DIR = ROOT_DIR / "results"

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
You are CLAUDE-FEATURE-BUILDER, an expert full-stack engineer.
You transform user stories into PRODUCTION-QUALITY CODE.

Tech Stack:
- Backend: FastAPI, SQLAlchemy 2.0 (async), PostgreSQL, Alembic
- Frontend: Next.js 14, React, TypeScript, Tailwind CSS
- Testing: pytest, pytest-asyncio, Playwright

When given a user story, output complete working code for:

1. **PRD Summary** - Brief requirements document
2. **System Design** - Architecture decisions
3. **Database Model** - SQLAlchemy model (backend/app/models/)
4. **Alembic Migration** - Migration file
5. **API Schema** - Pydantic schemas (backend/app/schemas/)
6. **Service Layer** - Business logic (backend/app/services/)
7. **API Endpoint** - FastAPI router (backend/app/api/v1/)
8. **Frontend Component** - React/Next.js page or component
9. **TypeScript Types** - Type definitions
10. **API Client** - Frontend API wrapper
11. **Unit Tests** - pytest tests
12. **Integration Tests** - API tests
13. **E2E Tests** - Playwright tests
14. **Documentation** - API docs and usage examples

Output Format:
For each file, use this format:

### FILE: path/to/file.ext
```language
<complete file content>
```

Rules:
- All code must be production-ready, not pseudocode
- Follow existing patterns in ABVTrends codebase
- Include proper error handling
- Add type hints to all Python functions
- Include docstrings for public functions
- Use async/await for database operations
- Follow REST API best practices
- Include data validation
- Consider edge cases and error states
"""


def read_existing_patterns() -> dict:
    """Read existing code patterns from the project."""

    patterns = {}

    # Read existing model pattern
    models_dir = BACKEND_DIR / "app" / "models"
    if models_dir.exists():
        for file in models_dir.glob("*.py"):
            if file.name != "__init__.py":
                try:
                    patterns["model_example"] = file.read_text()[:2000]
                    break
                except:
                    pass

    # Read existing API pattern
    api_dir = BACKEND_DIR / "app" / "api" / "v1"
    if api_dir.exists():
        for file in api_dir.glob("*.py"):
            if file.name != "__init__.py":
                try:
                    patterns["api_example"] = file.read_text()[:2000]
                    break
                except:
                    pass

    # Read existing service pattern
    services_dir = BACKEND_DIR / "app" / "services"
    if services_dir.exists():
        for file in services_dir.glob("*.py"):
            if file.name != "__init__.py":
                try:
                    patterns["service_example"] = file.read_text()[:2000]
                    break
                except:
                    pass

    # Read existing frontend pattern
    pages_dir = FRONTEND_DIR / "pages"
    if pages_dir.exists():
        for file in pages_dir.glob("*.tsx"):
            if file.name not in ["_app.tsx", "_document.tsx"]:
                try:
                    patterns["frontend_example"] = file.read_text()[:2000]
                    break
                except:
                    pass

    return patterns


def generate_feature(user_story: str) -> dict:
    """Generate complete feature from user story."""

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {"error": "ANTHROPIC_API_KEY not set"}

    print("Analyzing user story and generating feature...")

    # Get existing patterns for context
    patterns = read_existing_patterns()

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"""
Generate a complete feature implementation for ABVTrends.

## User Story
{user_story}

## Existing Code Patterns (for reference)

### Model Pattern
```python
{patterns.get('model_example', 'No model example available')}
```

### API Pattern
```python
{patterns.get('api_example', 'No API example available')}
```

### Service Pattern
```python
{patterns.get('service_example', 'No service example available')}
```

### Frontend Pattern
```typescript
{patterns.get('frontend_example', 'No frontend example available')}
```

## Project Structure
- backend/app/models/ - SQLAlchemy models
- backend/app/schemas/ - Pydantic schemas
- backend/app/services/ - Business logic
- backend/app/api/v1/ - FastAPI routers
- frontend/pages/ - Next.js pages
- frontend/components/ - React components
- frontend/services/ - API clients
- frontend/types/ - TypeScript types

Please generate all files needed for this feature.
"""
                }
            ]
        )

        content = response.content[0].text
        return parse_feature_output(content)

    except Exception as e:
        return {"error": str(e)}


def parse_feature_output(content: str) -> dict:
    """Parse Claude's output into structured files."""

    result = {
        "raw_output": content,
        "files": [],
        "prd": "",
        "design": ""
    }

    # Extract PRD section
    prd_match = re.search(r'\*\*PRD Summary\*\*[:\s]*(.*?)(?=\*\*|\n###|\Z)', content, re.DOTALL | re.IGNORECASE)
    if prd_match:
        result["prd"] = prd_match.group(1).strip()

    # Extract system design section
    design_match = re.search(r'\*\*System Design\*\*[:\s]*(.*?)(?=\*\*|\n###|\Z)', content, re.DOTALL | re.IGNORECASE)
    if design_match:
        result["design"] = design_match.group(1).strip()

    # Extract file blocks
    file_pattern = r'###\s*FILE:\s*([^\n]+)\n```(\w+)?\n(.*?)```'
    matches = re.findall(file_pattern, content, re.DOTALL)

    for file_path, language, file_content in matches:
        result["files"].append({
            "path": file_path.strip(),
            "language": language or "text",
            "content": file_content.strip()
        })

    return result


def save_feature_output(result: dict, user_story: str):
    """Save generated feature files."""

    RESULTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save raw output
    raw_file = RESULTS_DIR / f"feature_build_{timestamp}.md"
    with open(raw_file, "w") as f:
        f.write(f"# Feature Build Output\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")
        f.write(f"## User Story\n{user_story}\n\n")
        f.write("---\n\n")
        f.write(result.get("raw_output", ""))

    print(f"Raw output saved to: {raw_file}")

    # Save individual files to suggestions directory
    suggestions_dir = ROOT_DIR / "suggestions" / f"feature_{timestamp}"
    suggestions_dir.mkdir(parents=True, exist_ok=True)

    files_saved = []
    for file_info in result.get("files", []):
        file_path = file_info["path"]
        content = file_info["content"]

        # Create safe filename
        safe_name = file_path.replace("/", "_").replace("\\", "_")
        output_path = suggestions_dir / safe_name

        with open(output_path, "w") as f:
            f.write(content)

        files_saved.append({
            "original_path": file_path,
            "saved_to": str(output_path)
        })

    # Save manifest
    manifest_file = suggestions_dir / "manifest.json"
    with open(manifest_file, "w") as f:
        json.dump({
            "timestamp": timestamp,
            "user_story": user_story,
            "prd": result.get("prd", ""),
            "design": result.get("design", ""),
            "files": files_saved
        }, f, indent=2)

    print(f"Generated {len(files_saved)} files to: {suggestions_dir}")

    # Save summary report
    report_file = RESULTS_DIR / "feature_build_report.md"
    with open(report_file, "w") as f:
        f.write("# Feature Build Report\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")

        f.write("## User Story\n")
        f.write(f"{user_story}\n\n")

        if result.get("prd"):
            f.write("## PRD Summary\n")
            f.write(f"{result['prd']}\n\n")

        if result.get("design"):
            f.write("## System Design\n")
            f.write(f"{result['design']}\n\n")

        f.write("## Generated Files\n\n")
        f.write("| File | Language | Saved To |\n")
        f.write("|------|----------|----------|\n")
        for i, file_info in enumerate(result.get("files", [])):
            saved = files_saved[i] if i < len(files_saved) else {}
            f.write(f"| `{file_info['path']}` | {file_info['language']} | `{saved.get('saved_to', 'N/A')}` |\n")

        f.write(f"\n\n## Next Steps\n\n")
        f.write("1. Review generated code in `suggestions/feature_{timestamp}/`\n")
        f.write("2. Copy approved files to their target locations\n")
        f.write("3. Run migrations: `alembic upgrade head`\n")
        f.write("4. Run tests: `pytest` and `npm run test:e2e`\n")
        f.write("5. Update API documentation\n")

    print(f"Report saved to: {report_file}")

    return suggestions_dir


def apply_feature(suggestions_dir: Path, auto_apply: bool = False):
    """Apply generated feature files to the project."""

    manifest_file = suggestions_dir / "manifest.json"
    if not manifest_file.exists():
        print("No manifest found")
        return

    with open(manifest_file) as f:
        manifest = json.load(f)

    print(f"\nApplying feature from: {suggestions_dir}")

    for file_info in manifest.get("files", []):
        original_path = file_info["original_path"]
        saved_to = file_info["saved_to"]

        target_path = PROJECT_ROOT / original_path

        if not auto_apply:
            print(f"\nFile: {original_path}")
            response = input("Apply this file? (y/n/s=skip all): ").lower().strip()
            if response == 's':
                print("Skipping remaining files")
                break
            if response != 'y':
                continue

        # Create parent directories
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # Copy file
        import shutil
        shutil.copy(saved_to, target_path)
        print(f"Applied: {target_path}")


def main():
    """Main execution flow."""

    print("=" * 60)
    print("CLAUDE-FEATURE-BUILDER: AI Feature Code Generator")
    print("=" * 60)

    # Parse arguments
    auto_apply = "--auto-apply" in sys.argv
    apply_mode = "--apply" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    RESULTS_DIR.mkdir(exist_ok=True)

    # Check for feature request file
    request_file = SCRIPT_DIR / "feature_request.txt"

    if apply_mode and args:
        # Apply mode
        suggestions_dir = Path(args[0])
        apply_feature(suggestions_dir, auto_apply)
        return 0

    if args:
        # User story from argument
        user_story = " ".join(args)
    elif request_file.exists():
        # User story from file
        user_story = request_file.read_text().strip()
    else:
        print("\nUsage:")
        print("  python feature_builder.py 'Your user story here'")
        print("  python feature_builder.py  # reads from feature_request.txt")
        print("  python feature_builder.py --apply suggestions/feature_xxx/")
        print("\nCreate feature_request.txt with your user story:")
        print(f"  {request_file}")
        return 1

    print(f"\nUser Story:\n{user_story[:200]}...")

    # Generate feature
    result = generate_feature(user_story)

    if "error" in result:
        print(f"\nError: {result['error']}")
        return 1

    # Save output
    suggestions_dir = save_feature_output(result, user_story)

    print("\n" + "=" * 60)
    print("FEATURE GENERATION COMPLETE")
    print("=" * 60)
    print(f"Generated {len(result.get('files', []))} files")
    print(f"\nReview files in: {suggestions_dir}")
    print(f"\nTo apply: python feature_builder.py --apply {suggestions_dir}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
