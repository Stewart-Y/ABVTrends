#!/usr/bin/env python3
"""
CLAUDE-BACKEND-FIXER: AI Backend Bug Fixer

Analyzes Python stack traces and FastAPI errors, then generates corrected code.
Automatically locates the file causing errors and writes patches.
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

SYSTEM_PROMPT = """
You are CLAUDE-BACKEND-FIXER, an expert Python backend engineer.

Your responsibilities:
1. Analyze backend Python stack traces and error messages
2. Locate the correct file and line number causing the error
3. Generate a corrected version of the file
4. Fix common issues:
   - SQLAlchemy ORM errors (relationships, queries, sessions)
   - FastAPI routing and dependency injection
   - Async/await issues
   - Pydantic validation and schema errors
   - Type annotation errors
   - Import errors and circular dependencies
5. Improve robustness with proper error handling
6. Add logging for debugging

ABVTrends Backend Stack:
- FastAPI with async endpoints
- SQLAlchemy 2.0 with async support
- PostgreSQL database
- Pydantic v2 for validation
- Alembic for migrations

Output Format:
1. Error Analysis: Explain what went wrong
2. Root Cause: Identify the specific issue
3. File to Fix: The exact file path
4. Fixed Code: The complete corrected file content
5. Additional Recommendations: Any other improvements

Respond with valid JSON containing:
{
  "error_analysis": "...",
  "root_cause": "...",
  "file_path": "...",
  "fixed_code": "...",
  "recommendations": ["..."]
}
"""


def extract_file_from_traceback(trace: str) -> list[dict]:
    """Extract file paths and line numbers from Python traceback."""

    # Pattern to match Python traceback lines
    pattern = r'File "([^"]+)", line (\d+), in (\w+)'
    matches = re.findall(pattern, trace)

    files = []
    for filepath, line_num, func_name in matches:
        # Only include files from our backend
        if "backend" in filepath or "app" in filepath:
            files.append({
                "path": filepath,
                "line": int(line_num),
                "function": func_name
            })

    return files


def read_related_files(trace: str) -> dict[str, str]:
    """Read content of files mentioned in the traceback."""

    files_info = extract_file_from_traceback(trace)
    file_contents = {}

    for file_info in files_info:
        filepath = file_info["path"]

        # Try to find the file
        possible_paths = [
            Path(filepath),
            BACKEND_DIR / filepath.split("backend/")[-1] if "backend/" in filepath else None,
            BACKEND_DIR / "app" / filepath.split("app/")[-1] if "app/" in filepath else None,
        ]

        for path in possible_paths:
            if path and path.exists():
                try:
                    content = path.read_text()
                    file_contents[str(path)] = content
                    break
                except:
                    continue

    return file_contents


def fix_backend_error(trace: str, additional_context: str = "") -> dict:
    """Send error trace to Claude for analysis and fixing."""

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {"error": "ANTHROPIC_API_KEY not set"}

    # Read related files
    related_files = read_related_files(trace)

    print(f"Analyzing error trace...")
    print(f"Found {len(related_files)} related files")

    # Build context message
    context = f"""
## Error Traceback
```
{trace}
```

## Related Files Content
"""

    for filepath, content in related_files.items():
        context += f"\n### {filepath}\n```python\n{content}\n```\n"

    if additional_context:
        context += f"\n## Additional Context\n{additional_context}\n"

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": context
                }
            ]
        )

        content = response.content[0].text

        # Try to parse JSON response
        try:
            # Find JSON in response
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

        return {"raw_response": content}

    except Exception as e:
        return {"error": str(e)}


def apply_fix(fix_result: dict, auto_apply: bool = False) -> bool:
    """Apply the suggested fix to the file."""

    if "error" in fix_result:
        print(f"Error: {fix_result['error']}")
        return False

    if "raw_response" in fix_result:
        print("Could not parse structured response. Raw output:")
        print(fix_result["raw_response"])
        return False

    file_path = fix_result.get("file_path", "")
    fixed_code = fix_result.get("fixed_code", "")

    if not file_path or not fixed_code:
        print("Missing file path or fixed code in response")
        return False

    # Display analysis
    print("\n" + "=" * 60)
    print("ERROR ANALYSIS")
    print("=" * 60)
    print(fix_result.get("error_analysis", "N/A"))

    print("\n" + "=" * 60)
    print("ROOT CAUSE")
    print("=" * 60)
    print(fix_result.get("root_cause", "N/A"))

    print("\n" + "=" * 60)
    print(f"FILE TO FIX: {file_path}")
    print("=" * 60)

    print("\nRECOMMENDATIONS:")
    for rec in fix_result.get("recommendations", []):
        print(f"  - {rec}")

    # Find the actual file path
    target_path = None
    possible_paths = [
        Path(file_path),
        BACKEND_DIR / file_path.split("backend/")[-1] if "backend/" in file_path else None,
        BACKEND_DIR / file_path if not file_path.startswith("/") else None,
    ]

    for path in possible_paths:
        if path and path.exists():
            target_path = path
            break

    if not target_path:
        # Save to suggestions if we can't find the file
        print(f"\nCould not locate file: {file_path}")
        print("Saving fix to suggestions directory...")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suggestion_file = SUGGESTIONS_DIR / f"backend_fix_{timestamp}.py"
        SUGGESTIONS_DIR.mkdir(exist_ok=True)

        with open(suggestion_file, "w") as f:
            f.write(f"# Fix for: {file_path}\n")
            f.write(f"# Generated: {datetime.now().isoformat()}\n\n")
            f.write(fixed_code)

        print(f"Saved to: {suggestion_file}")
        return True

    # Confirm before applying
    if not auto_apply:
        print(f"\nTarget file: {target_path}")
        print("\nFixed code preview (first 50 lines):")
        print("-" * 40)
        lines = fixed_code.split("\n")[:50]
        print("\n".join(lines))
        if len(fixed_code.split("\n")) > 50:
            print("... (truncated)")
        print("-" * 40)

        response = input("\nApply this fix? (y/n): ").lower().strip()
        if response != 'y':
            # Save to suggestions instead
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            suggestion_file = SUGGESTIONS_DIR / f"backend_fix_{timestamp}.py"
            SUGGESTIONS_DIR.mkdir(exist_ok=True)

            with open(suggestion_file, "w") as f:
                f.write(fixed_code)

            print(f"Fix saved to: {suggestion_file}")
            return True

    # Apply the fix
    try:
        # Backup original file
        backup_path = target_path.with_suffix(target_path.suffix + ".bak")
        if target_path.exists():
            import shutil
            shutil.copy(target_path, backup_path)
            print(f"Backup created: {backup_path}")

        # Write fixed code
        with open(target_path, "w") as f:
            f.write(fixed_code)

        print(f"Fix applied to: {target_path}")
        return True

    except Exception as e:
        print(f"Error applying fix: {e}")
        return False


def save_analysis(fix_result: dict, trace: str):
    """Save the analysis report."""

    RESULTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save JSON result
    json_file = RESULTS_DIR / f"backend_fix_{timestamp}.json"
    with open(json_file, "w") as f:
        json.dump(fix_result, f, indent=2)

    # Save markdown report
    report_file = RESULTS_DIR / f"backend_fix_{timestamp}.md"
    with open(report_file, "w") as f:
        f.write(f"# Backend Error Fix Report\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")
        f.write("## Original Error\n```\n")
        f.write(trace[:2000])
        f.write("\n```\n\n")

        if "error_analysis" in fix_result:
            f.write("## Error Analysis\n")
            f.write(fix_result["error_analysis"])
            f.write("\n\n")

        if "root_cause" in fix_result:
            f.write("## Root Cause\n")
            f.write(fix_result["root_cause"])
            f.write("\n\n")

        if "file_path" in fix_result:
            f.write(f"## File to Fix\n`{fix_result['file_path']}`\n\n")

        if "recommendations" in fix_result:
            f.write("## Recommendations\n")
            for rec in fix_result["recommendations"]:
                f.write(f"- {rec}\n")

    print(f"\nAnalysis saved to: {report_file}")


def main():
    """Main execution flow."""

    print("=" * 60)
    print("CLAUDE-BACKEND-FIXER: AI Backend Bug Fixer")
    print("=" * 60)

    # Parse arguments
    auto_apply = "--auto-apply" in sys.argv

    # Check for error log file
    error_log = RESULTS_DIR / "backend_error.log"

    if len(sys.argv) > 1 and sys.argv[1] not in ["--auto-apply"]:
        # Read from specified file
        error_log = Path(sys.argv[1])

    if not error_log.exists():
        # Try to read from stdin or prompt
        print(f"\nNo error log found at {error_log}")
        print("Paste the error traceback (end with Ctrl+D or empty line):\n")

        lines = []
        try:
            while True:
                line = input()
                if not line:
                    break
                lines.append(line)
        except EOFError:
            pass

        trace = "\n".join(lines)

        if not trace.strip():
            print("No error trace provided")
            return 1
    else:
        print(f"Reading error from: {error_log}")
        trace = error_log.read_text()

    # Analyze and fix
    fix_result = fix_backend_error(trace)

    # Save analysis
    save_analysis(fix_result, trace)

    # Apply fix
    if "error" not in fix_result:
        apply_fix(fix_result, auto_apply)

    print("\n" + "=" * 60)
    print("Backend fix analysis complete!")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
