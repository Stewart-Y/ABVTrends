#!/usr/bin/env python3
"""
CLAUDE-REFACTOR: AI Backend Refactoring Agent

Improves code architecture, removes code smells, and enhances quality.
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
You are CLAUDE-REFACTOR, an expert Python code architect.

Your goals:
1. Improve readability and maintainability
2. Improve performance where possible
3. Reduce complexity (cyclomatic, cognitive)
4. Fix architecture smells
5. Enhance async usage patterns
6. Reduce duplicate code (DRY)
7. Add helpful comments and docstrings
8. Improve type annotations
9. Apply SOLID principles
10. Follow FastAPI and SQLAlchemy best practices

ABVTrends Context:
- FastAPI async backend
- SQLAlchemy 2.0 async ORM
- Pydantic v2 validation
- PostgreSQL database
- Service-repository pattern encouraged

Refactoring Categories:
- Extract Method: Long functions -> smaller focused functions
- Extract Class: Related functionality -> new class
- Rename: Improve naming clarity
- Move: Better module organization
- Simplify Conditionals: Complex if/else -> cleaner patterns
- Remove Duplication: DRY violations
- Improve Async: Sync calls in async context
- Type Safety: Add/improve type hints

Output Format:
1. Analysis of current code issues
2. Refactoring plan with justifications
3. Complete refactored code
4. Migration notes (if breaking changes)

Return valid JSON:
{
  "file_path": "...",
  "analysis": {
    "issues": ["..."],
    "complexity_score": "high|medium|low",
    "maintainability": "..."
  },
  "refactoring_plan": [
    {
      "type": "extract_method|rename|simplify|...",
      "description": "...",
      "impact": "high|medium|low"
    }
  ],
  "refactored_code": "...",
  "migration_notes": ["..."]
}
"""


def analyze_code_quality(file_path: Path) -> dict:
    """Analyze code quality metrics."""

    content = file_path.read_text()

    metrics = {
        "lines": len(content.splitlines()),
        "functions": len(re.findall(r'def\s+\w+', content)),
        "classes": len(re.findall(r'class\s+\w+', content)),
        "imports": len(re.findall(r'^import|^from', content, re.MULTILINE)),
        "complexity_indicators": {
            "nested_loops": len(re.findall(r'for.*:\s*\n\s+for', content)),
            "deep_nesting": len(re.findall(r'^\s{16,}', content, re.MULTILINE)),
            "long_functions": 0,
            "god_objects": 0,
        }
    }

    # Check for long functions
    func_pattern = r'def\s+\w+[^:]+:\s*\n((?:\s+.*\n)+)'
    for match in re.finditer(func_pattern, content):
        func_body = match.group(1)
        if len(func_body.splitlines()) > 50:
            metrics["complexity_indicators"]["long_functions"] += 1

    # Check for classes with too many methods
    class_pattern = r'class\s+\w+[^:]*:\s*\n((?:\s+.*\n)+)'
    for match in re.finditer(class_pattern, content):
        class_body = match.group(1)
        method_count = len(re.findall(r'def\s+\w+', class_body))
        if method_count > 10:
            metrics["complexity_indicators"]["god_objects"] += 1

    return metrics


def refactor_file(file_path: str) -> dict:
    """Refactor a specific file with Claude."""

    path = Path(file_path)
    if not path.is_absolute():
        path = BACKEND_DIR / file_path

    if not path.exists():
        return {"error": f"File not found: {path}"}

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {"error": "ANTHROPIC_API_KEY not set"}

    print(f"Analyzing: {path}")

    content = path.read_text()
    metrics = analyze_code_quality(path)

    print(f"  Lines: {metrics['lines']}")
    print(f"  Functions: {metrics['functions']}")
    print(f"  Complexity indicators: {sum(metrics['complexity_indicators'].values())}")

    print("\nSending to Claude for refactoring...")

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"""
Refactor the following Python file from ABVTrends backend.

## File: {path.relative_to(BACKEND_DIR) if path.is_relative_to(BACKEND_DIR) else path}

## Current Code Quality Metrics:
{json.dumps(metrics, indent=2)}

## Code:
```python
{content}
```

Please:
1. Analyze code issues and smells
2. Create a refactoring plan
3. Provide the complete refactored code
4. Note any migration requirements

Return your response as JSON.
"""
                }
            ]
        )

        response_content = response.content[0].text

        # Try to parse JSON
        try:
            json_match = re.search(r'\{[\s\S]*\}', response_content)
            if json_match:
                result = json.loads(json_match.group())
                result["original_metrics"] = metrics
                return result
        except json.JSONDecodeError:
            pass

        return {"raw_response": response_content, "original_metrics": metrics}

    except Exception as e:
        return {"error": str(e)}


def save_refactoring(result: dict, original_path: str):
    """Save refactoring results."""

    SUGGESTIONS_DIR.mkdir(exist_ok=True)
    RESULTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    original_name = Path(original_path).stem

    # Save refactored code
    if "refactored_code" in result:
        refactored_file = SUGGESTIONS_DIR / f"refactored_{original_name}_{timestamp}.py"
        with open(refactored_file, "w") as f:
            f.write(f"# Refactored from: {original_path}\n")
            f.write(f"# Generated: {datetime.now().isoformat()}\n\n")
            f.write(result["refactored_code"])
        print(f"\nRefactored code saved to: {refactored_file}")

    # Save analysis report
    report_file = RESULTS_DIR / f"refactor_report_{original_name}_{timestamp}.md"
    with open(report_file, "w") as f:
        f.write(f"# Refactoring Report: {original_name}\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")

        if "analysis" in result:
            f.write("## Analysis\n\n")
            analysis = result["analysis"]

            if "issues" in analysis:
                f.write("### Issues Found\n")
                for issue in analysis["issues"]:
                    f.write(f"- {issue}\n")
                f.write("\n")

            f.write(f"**Complexity:** {analysis.get('complexity_score', 'N/A')}\n")
            f.write(f"**Maintainability:** {analysis.get('maintainability', 'N/A')}\n\n")

        if "refactoring_plan" in result:
            f.write("## Refactoring Plan\n\n")
            for item in result["refactoring_plan"]:
                impact = item.get("impact", "medium")
                f.write(f"### [{impact.upper()}] {item.get('type', 'Unknown')}\n")
                f.write(f"{item.get('description', 'N/A')}\n\n")

        if "migration_notes" in result:
            f.write("## Migration Notes\n\n")
            for note in result["migration_notes"]:
                f.write(f"- {note}\n")

        if "original_metrics" in result:
            f.write("\n## Original Metrics\n")
            f.write(f"```json\n{json.dumps(result['original_metrics'], indent=2)}\n```\n")

        if "raw_response" in result:
            f.write("\n## Raw Analysis\n\n")
            f.write(result["raw_response"])

    print(f"Report saved to: {report_file}")


def apply_refactoring(result: dict, original_path: str, auto_apply: bool = False) -> bool:
    """Apply refactored code to the original file."""

    if "refactored_code" not in result:
        print("No refactored code to apply")
        return False

    path = Path(original_path)
    if not path.is_absolute():
        path = BACKEND_DIR / original_path

    if not path.exists():
        print(f"Original file not found: {path}")
        return False

    if not auto_apply:
        print("\n" + "=" * 60)
        print("REFACTORING PREVIEW")
        print("=" * 60)

        if "refactoring_plan" in result:
            print("\nPlanned changes:")
            for item in result["refactoring_plan"]:
                print(f"  - [{item.get('impact', 'medium').upper()}] {item.get('type')}: {item.get('description')}")

        if "migration_notes" in result and result["migration_notes"]:
            print("\nMigration notes:")
            for note in result["migration_notes"]:
                print(f"  - {note}")

        response = input(f"\nApply refactoring to {path}? (y/n): ").lower().strip()
        if response != 'y':
            print("Skipped applying changes")
            return False

    # Create backup
    backup_path = path.with_suffix(path.suffix + ".bak")
    import shutil
    shutil.copy(path, backup_path)
    print(f"Backup created: {backup_path}")

    # Apply changes
    try:
        with open(path, "w") as f:
            f.write(result["refactored_code"])
        print(f"Refactoring applied to: {path}")
        return True
    except Exception as e:
        print(f"Error applying changes: {e}")
        # Restore backup
        shutil.copy(backup_path, path)
        print("Restored from backup")
        return False


def main():
    """Main execution flow."""

    print("=" * 60)
    print("CLAUDE-REFACTOR: AI Backend Refactoring Agent")
    print("=" * 60)

    # Parse arguments
    auto_apply = "--auto-apply" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    if not args:
        print("\nUsage: python refactor_agent.py <file_path> [--auto-apply]")
        print("\nExamples:")
        print("  python refactor_agent.py app/services/trend_engine.py")
        print("  python refactor_agent.py app/services/signal_processor.py --auto-apply")
        print("\nAvailable files to refactor:")

        # List some key files
        services_dir = BACKEND_DIR / "app" / "services"
        if services_dir.exists():
            for f in services_dir.glob("*.py"):
                if not f.name.startswith("_"):
                    print(f"  app/services/{f.name}")

        return 1

    file_path = args[0]

    # Run refactoring
    result = refactor_file(file_path)

    if "error" in result:
        print(f"\nError: {result['error']}")
        return 1

    # Save results
    save_refactoring(result, file_path)

    # Optionally apply
    if auto_apply or input("\nWould you like to apply the refactoring? (y/n): ").lower() == 'y':
        apply_refactoring(result, file_path, auto_apply)

    print("\n" + "=" * 60)
    print("Refactoring complete!")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
