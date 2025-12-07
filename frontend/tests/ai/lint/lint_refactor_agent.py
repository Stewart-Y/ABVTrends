#!/usr/bin/env python3
"""
CLAUDE-LINT-MASTER: AI Lint + Style Refactoring Agent

Rewrites Python/TypeScript files to conform to:
- PEP8 / Black formatting
- Pylint / Ruff rules
- Proper type hints
- Comprehensive docstrings
- Clean code principles
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
SUGGESTIONS_DIR = ROOT_DIR / "suggestions"

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

PYTHON_SYSTEM_PROMPT = """
You are CLAUDE-LINT-MASTER, an expert Python code quality engineer.

You apply:
1. PEP8 style guidelines
2. Black-compatible formatting
3. Comprehensive type hints (Python 3.9+ style)
4. Google-style docstrings
5. Proper import organization (stdlib, third-party, local)
6. Remove unused imports
7. Simplify complex logic
8. Improve naming consistency
9. Fix async/await patterns
10. Apply SOLID principles where appropriate

Rules:
- Line length: 88 characters (Black default)
- Use f-strings instead of % or .format()
- Use pathlib instead of os.path where applicable
- Prefer explicit over implicit
- Add type hints to all function signatures
- Add docstrings to all public functions/classes
- Use snake_case for functions/variables, PascalCase for classes
- Organize imports: stdlib, third-party, local (blank line between each)

Output:
Return ONLY the complete corrected file content.
Do not include explanations or markdown formatting.
Just the raw Python code.
"""

TYPESCRIPT_SYSTEM_PROMPT = """
You are CLAUDE-LINT-MASTER, an expert TypeScript code quality engineer.

You apply:
1. ESLint recommended rules
2. Prettier formatting
3. Comprehensive TypeScript types
4. JSDoc comments for public APIs
5. Proper import organization
6. Remove unused imports/variables
7. Simplify complex logic
8. Improve naming consistency
9. Fix async/await patterns
10. Apply React best practices (for .tsx files)

Rules:
- Use const over let where possible
- Use arrow functions for callbacks
- Use template literals instead of concatenation
- Prefer interfaces over type aliases for objects
- Use explicit return types on functions
- Add JSDoc for public functions
- Use camelCase for functions/variables, PascalCase for components/classes
- Organize imports: react, libraries, local (blank line between each)

Output:
Return ONLY the complete corrected file content.
Do not include explanations or markdown formatting.
Just the raw TypeScript/JavaScript code.
"""


def detect_file_type(file_path: Path) -> str:
    """Detect file type from extension."""

    suffix = file_path.suffix.lower()

    if suffix == ".py":
        return "python"
    elif suffix in [".ts", ".tsx"]:
        return "typescript"
    elif suffix in [".js", ".jsx"]:
        return "javascript"
    else:
        return "unknown"


def lint_file(file_path: Path) -> dict:
    """Lint and refactor a single file."""

    if not file_path.exists():
        return {"error": f"File not found: {file_path}"}

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {"error": "ANTHROPIC_API_KEY not set"}

    file_type = detect_file_type(file_path)

    if file_type == "unknown":
        return {"error": f"Unsupported file type: {file_path.suffix}"}

    print(f"  Linting: {file_path.name} ({file_type})")

    content = file_path.read_text()

    # Select appropriate system prompt
    if file_type == "python":
        system_prompt = PYTHON_SYSTEM_PROMPT
    else:
        system_prompt = TYPESCRIPT_SYSTEM_PROMPT

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=12000,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": f"""
Lint and refactor this {file_type} file. Apply all style rules and best practices.

File: {file_path.name}

```{file_type}
{content}
```

Return ONLY the corrected code, no explanations.
"""
                }
            ]
        )

        linted_content = response.content[0].text

        # Clean up response (remove any markdown formatting)
        linted_content = re.sub(r'^```\w*\n', '', linted_content)
        linted_content = re.sub(r'\n```$', '', linted_content)
        linted_content = linted_content.strip()

        return {
            "file_path": str(file_path),
            "file_type": file_type,
            "original_lines": len(content.splitlines()),
            "linted_lines": len(linted_content.splitlines()),
            "linted_content": linted_content
        }

    except Exception as e:
        return {"error": str(e)}


def analyze_changes(original: str, linted: str) -> dict:
    """Analyze differences between original and linted code."""

    original_lines = original.splitlines()
    linted_lines = linted.splitlines()

    changes = {
        "lines_added": max(0, len(linted_lines) - len(original_lines)),
        "lines_removed": max(0, len(original_lines) - len(linted_lines)),
        "imports_changed": False,
        "docstrings_added": False,
        "type_hints_added": False
    }

    # Check for import changes
    orig_imports = [l for l in original_lines if l.strip().startswith(('import ', 'from '))]
    lint_imports = [l for l in linted_lines if l.strip().startswith(('import ', 'from '))]
    changes["imports_changed"] = orig_imports != lint_imports

    # Check for docstring additions
    orig_docstrings = original.count('"""')
    lint_docstrings = linted.count('"""')
    changes["docstrings_added"] = lint_docstrings > orig_docstrings

    # Check for type hint additions
    orig_hints = len(re.findall(r'def \w+\([^)]*:', original))
    lint_hints = len(re.findall(r'def \w+\([^)]*\)\s*->', linted))
    changes["type_hints_added"] = lint_hints > 0

    return changes


def lint_directory(directory: Path, patterns: list = None) -> list:
    """Lint all matching files in a directory."""

    if patterns is None:
        patterns = ["**/*.py"]

    results = []

    for pattern in patterns:
        for file_path in directory.glob(pattern):
            # Skip common directories
            if any(x in str(file_path) for x in ["node_modules", "venv", "__pycache__", ".git"]):
                continue

            result = lint_file(file_path)
            results.append(result)

    return results


def save_linted_file(result: dict, output_dir: Path = None) -> Path:
    """Save linted file to suggestions directory."""

    if "error" in result:
        return None

    if output_dir is None:
        output_dir = SUGGESTIONS_DIR

    output_dir.mkdir(exist_ok=True)

    original_path = Path(result["file_path"])
    output_file = output_dir / f"linted_{original_path.name}"

    with open(output_file, "w") as f:
        f.write(result["linted_content"])

    return output_file


def apply_lint(result: dict, auto_apply: bool = False) -> bool:
    """Apply linted code to original file."""

    if "error" in result:
        print(f"Cannot apply: {result['error']}")
        return False

    file_path = Path(result["file_path"])

    if not file_path.exists():
        print(f"Original file not found: {file_path}")
        return False

    if not auto_apply:
        original = file_path.read_text()
        changes = analyze_changes(original, result["linted_content"])

        print(f"\nChanges for {file_path.name}:")
        print(f"  Lines: {result['original_lines']} -> {result['linted_lines']}")
        print(f"  Imports changed: {changes['imports_changed']}")
        print(f"  Docstrings added: {changes['docstrings_added']}")
        print(f"  Type hints added: {changes['type_hints_added']}")

        response = input("\nApply these changes? (y/n): ").lower().strip()
        if response != 'y':
            print("Skipped")
            return False

    # Create backup
    backup_path = file_path.with_suffix(file_path.suffix + ".bak")
    import shutil
    shutil.copy(file_path, backup_path)

    # Apply changes
    with open(file_path, "w") as f:
        f.write(result["linted_content"])

    print(f"Applied lint to: {file_path}")
    return True


def main():
    """Main execution flow."""

    print("=" * 60)
    print("CLAUDE-LINT-MASTER: AI Lint + Style Agent")
    print("=" * 60)

    # Parse arguments
    auto_apply = "--auto-apply" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    RESULTS_DIR.mkdir(exist_ok=True)
    SUGGESTIONS_DIR.mkdir(exist_ok=True)

    if not args:
        print("\nUsage: python lint_refactor_agent.py <file_or_directory> [--auto-apply]")
        print("\nExamples:")
        print("  python lint_refactor_agent.py backend/app/services/trend_engine.py")
        print("  python lint_refactor_agent.py backend/app/services/ --auto-apply")
        print("\nAvailable targets:")
        print(f"  Backend: {BACKEND_DIR / 'app'}")
        print(f"  Frontend: {FRONTEND_DIR / 'pages'}")
        return 1

    target = Path(args[0])

    # Make path absolute if relative
    if not target.is_absolute():
        if target.exists():
            target = target.resolve()
        elif (PROJECT_ROOT / target).exists():
            target = PROJECT_ROOT / target
        elif (BACKEND_DIR / target).exists():
            target = BACKEND_DIR / target

    if not target.exists():
        print(f"Target not found: {target}")
        return 1

    results = []

    if target.is_file():
        # Lint single file
        print(f"\nLinting file: {target}")
        result = lint_file(target)
        results.append(result)
    else:
        # Lint directory
        print(f"\nLinting directory: {target}")
        patterns = ["**/*.py"] if "backend" in str(target) else ["**/*.ts", "**/*.tsx"]
        results = lint_directory(target, patterns)

    # Process results
    success_count = 0
    error_count = 0

    for result in results:
        if "error" in result:
            print(f"  Error: {result['error']}")
            error_count += 1
        else:
            # Save to suggestions
            saved = save_linted_file(result)
            if saved:
                print(f"  Saved: {saved}")
            success_count += 1

            # Apply if requested
            if auto_apply:
                apply_lint(result, auto_apply=True)

    # Save summary
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_file = RESULTS_DIR / f"lint_summary_{timestamp}.json"
    with open(summary_file, "w") as f:
        json.dump({
            "timestamp": timestamp,
            "target": str(target),
            "files_processed": len(results),
            "success": success_count,
            "errors": error_count,
            "results": [
                {k: v for k, v in r.items() if k != "linted_content"}
                for r in results
            ]
        }, f, indent=2)

    print("\n" + "=" * 60)
    print("LINT COMPLETE")
    print("=" * 60)
    print(f"Files processed: {len(results)}")
    print(f"Success: {success_count}")
    print(f"Errors: {error_count}")
    print(f"\nLinted files saved to: {SUGGESTIONS_DIR}")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
