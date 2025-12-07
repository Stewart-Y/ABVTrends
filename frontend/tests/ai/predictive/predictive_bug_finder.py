#!/usr/bin/env python3
"""
CLAUDE-BUG-PROPHET: AI Predictive Bug Finder

Analyzes code to detect potential bugs BEFORE they cause runtime errors:
- Exception handling gaps
- Async deadlocks
- SQL injection risks
- Memory leaks
- Race conditions
- Data inconsistency risks
- Scalability bottlenecks
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
You are CLAUDE-BUG-PROPHET, an expert at predicting bugs before they occur.

You analyze code to find:

1. **Exception Handling Issues**
   - Unhandled exceptions
   - Bare except clauses
   - Missing error recovery
   - Incomplete try-except blocks

2. **Async/Concurrency Issues**
   - Potential deadlocks
   - Race conditions
   - Missing await statements
   - Event loop blocking
   - Thread safety issues

3. **Database Issues**
   - SQL injection vulnerabilities
   - N+1 query problems
   - Missing transactions
   - Connection leaks
   - Improper session handling

4. **Memory Issues**
   - Memory leaks
   - Unbounded data structures
   - Large object creation in loops
   - Missing cleanup

5. **Logic Errors**
   - Off-by-one errors
   - Null/None reference risks
   - Type confusion
   - Invalid state transitions
   - Edge cases not handled

6. **Security Issues**
   - Input validation gaps
   - Authentication bypasses
   - Authorization issues
   - Data exposure risks

7. **Scalability Issues**
   - O(n²) algorithms
   - Missing pagination
   - Unbounded queries
   - Resource exhaustion

8. **API Issues**
   - Missing validation
   - Inconsistent error responses
   - Breaking changes risk
   - Missing rate limiting

Tech Context:
- FastAPI with async SQLAlchemy 2.0
- PostgreSQL database
- Next.js frontend
- Redis caching (optional)

Output Format (JSON):
{
  "summary": {
    "files_analyzed": 0,
    "potential_bugs": 0,
    "critical": 0,
    "high": 0,
    "medium": 0,
    "low": 0,
    "risk_score": 0-100
  },
  "bugs": [
    {
      "id": "BUG-001",
      "severity": "critical|high|medium|low",
      "category": "exception|async|database|memory|logic|security|scalability|api",
      "file": "path/to/file.py",
      "line": 123,
      "code_snippet": "problematic code",
      "description": "What could go wrong",
      "impact": "What happens if bug occurs",
      "likelihood": "high|medium|low",
      "fix": "How to fix it",
      "fixed_code": "corrected code snippet"
    }
  ],
  "patterns": [
    {
      "pattern": "Anti-pattern name",
      "occurrences": 0,
      "files": ["..."],
      "recommendation": "..."
    }
  ],
  "recommendations": [
    {
      "priority": "high|medium|low",
      "area": "...",
      "description": "...",
      "implementation": "..."
    }
  ]
}
"""


def scan_python_files(directory: Path) -> dict:
    """Scan Python files and collect code."""

    files_content = {}

    for file in directory.rglob("*.py"):
        # Skip common directories
        if any(x in str(file) for x in ["venv", "__pycache__", ".git", "node_modules", "tests/ai"]):
            continue

        try:
            content = file.read_text()
            relative_path = file.relative_to(PROJECT_ROOT)
            files_content[str(relative_path)] = content
        except Exception:
            pass

    return files_content


def scan_typescript_files(directory: Path) -> dict:
    """Scan TypeScript files and collect code."""

    files_content = {}

    for file in directory.rglob("*.tsx"):
        if "node_modules" in str(file):
            continue

        try:
            content = file.read_text()
            relative_path = file.relative_to(PROJECT_ROOT)
            files_content[str(relative_path)] = content
        except Exception:
            pass

    for file in directory.rglob("*.ts"):
        if "node_modules" in str(file):
            continue

        try:
            content = file.read_text()
            relative_path = file.relative_to(PROJECT_ROOT)
            files_content[str(relative_path)] = content
        except Exception:
            pass

    return files_content


def quick_pattern_scan(content: str) -> list:
    """Quick scan for common bug patterns."""

    patterns = []

    # Bare except
    if re.search(r'except\s*:', content):
        patterns.append("bare_except")

    # Missing await
    if re.search(r'async\s+def', content) and re.search(r'(?<!await\s)\w+\.(execute|fetch|commit)\(', content):
        patterns.append("possibly_missing_await")

    # SQL string formatting (injection risk)
    if re.search(r'f["\'].*SELECT.*\{', content) or re.search(r'%s.*SELECT|SELECT.*%s', content):
        patterns.append("sql_string_formatting")

    # No type hints
    if re.search(r'def\s+\w+\([^)]*\)\s*:', content) and not re.search(r'def\s+\w+\([^)]*\)\s*->', content):
        patterns.append("missing_type_hints")

    # Large file
    if len(content) > 500:
        patterns.append("large_function_risk")

    return patterns


def analyze_bugs(python_files: dict, typescript_files: dict) -> dict:
    """Analyze code for potential bugs with Claude."""

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {"error": "ANTHROPIC_API_KEY not set"}

    print("Analyzing code for potential bugs...")

    # Prepare code summary
    code_content = ""

    # Add Python files
    for path, content in list(python_files.items())[:20]:  # Limit files
        quick_patterns = quick_pattern_scan(content)
        code_content += f"\n### FILE: {path}\n"
        if quick_patterns:
            code_content += f"Quick scan patterns: {', '.join(quick_patterns)}\n"
        code_content += f"```python\n{content[:4000]}\n```\n"

    # Add TypeScript files
    for path, content in list(typescript_files.items())[:10]:
        code_content += f"\n### FILE: {path}\n"
        code_content += f"```typescript\n{content[:3000]}\n```\n"

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=12000,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"""
Analyze this codebase for potential bugs and issues.

## Project: ABVTrends
An AI-powered alcohol trend forecasting platform.

## Files Analyzed
Python files: {len(python_files)}
TypeScript files: {len(typescript_files)}

## Code Content
{code_content[:50000]}

Please analyze for:
1. Critical bugs that could cause failures
2. Security vulnerabilities
3. Performance issues
4. Code quality problems
5. Anti-patterns

Return your analysis as JSON.
"""
                }
            ]
        )

        content = response.content[0].text

        # Parse JSON
        try:
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

        return {"raw_response": content}

    except Exception as e:
        return {"error": str(e)}


def save_bug_report(analysis: dict, python_files: dict, typescript_files: dict):
    """Save bug analysis report."""

    RESULTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save JSON
    json_file = RESULTS_DIR / f"predictive_bugs_{timestamp}.json"
    with open(json_file, "w") as f:
        json.dump(analysis, f, indent=2)

    # Save markdown report
    report_file = RESULTS_DIR / "predictive_bug_report.md"
    with open(report_file, "w") as f:
        f.write("# Predictive Bug Analysis Report\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")

        if "summary" in analysis:
            summary = analysis["summary"]
            f.write("## Summary\n\n")
            f.write(f"- **Files Analyzed:** {summary.get('files_analyzed', len(python_files) + len(typescript_files))}\n")
            f.write(f"- **Potential Bugs:** {summary.get('potential_bugs', 'N/A')}\n")
            f.write(f"- **Risk Score:** {summary.get('risk_score', 'N/A')}/100\n\n")

            f.write("### Severity Breakdown\n")
            f.write(f"- 🔴 Critical: {summary.get('critical', 0)}\n")
            f.write(f"- 🟠 High: {summary.get('high', 0)}\n")
            f.write(f"- 🟡 Medium: {summary.get('medium', 0)}\n")
            f.write(f"- 🟢 Low: {summary.get('low', 0)}\n\n")

        if "bugs" in analysis and analysis["bugs"]:
            f.write("## Potential Bugs Found\n\n")

            # Group by severity
            for severity in ["critical", "high", "medium", "low"]:
                bugs = [b for b in analysis["bugs"] if b.get("severity") == severity]
                if bugs:
                    emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(severity, "")
                    f.write(f"### {emoji} {severity.upper()} Severity\n\n")

                    for bug in bugs:
                        f.write(f"#### {bug.get('id', 'BUG')}: {bug.get('category', 'Unknown')}\n")
                        f.write(f"**File:** `{bug.get('file', 'N/A')}`")
                        if bug.get("line"):
                            f.write(f" (line {bug['line']})")
                        f.write("\n\n")

                        f.write(f"**Description:** {bug.get('description', 'N/A')}\n\n")
                        f.write(f"**Impact:** {bug.get('impact', 'N/A')}\n\n")
                        f.write(f"**Likelihood:** {bug.get('likelihood', 'N/A')}\n\n")

                        if bug.get("code_snippet"):
                            f.write(f"**Problematic Code:**\n```python\n{bug['code_snippet']}\n```\n\n")

                        f.write(f"**Fix:** {bug.get('fix', 'N/A')}\n\n")

                        if bug.get("fixed_code"):
                            f.write(f"**Fixed Code:**\n```python\n{bug['fixed_code']}\n```\n\n")

                        f.write("---\n\n")

        if "patterns" in analysis and analysis["patterns"]:
            f.write("## Anti-Patterns Detected\n\n")
            f.write("| Pattern | Occurrences | Files |\n")
            f.write("|---------|-------------|-------|\n")
            for pattern in analysis["patterns"]:
                files = ", ".join(pattern.get("files", [])[:3])
                if len(pattern.get("files", [])) > 3:
                    files += "..."
                f.write(f"| {pattern.get('pattern', 'N/A')} | {pattern.get('occurrences', 0)} | {files} |\n")
            f.write("\n")

        if "recommendations" in analysis:
            f.write("## Recommendations\n\n")
            for rec in analysis["recommendations"]:
                priority = rec.get("priority", "medium")
                emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(priority, "")
                f.write(f"### {emoji} [{priority.upper()}] {rec.get('area', 'General')}\n")
                f.write(f"{rec.get('description', 'N/A')}\n\n")
                if rec.get("implementation"):
                    f.write(f"**Implementation:**\n{rec['implementation']}\n\n")

        if "raw_response" in analysis:
            f.write("## Raw Analysis\n\n")
            f.write(analysis["raw_response"])

    print(f"Bug report saved to: {report_file}")
    return report_file


def main():
    """Main execution flow."""

    print("=" * 60)
    print("CLAUDE-BUG-PROPHET: AI Predictive Bug Finder")
    print("=" * 60)

    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    RESULTS_DIR.mkdir(exist_ok=True)

    # Determine target directory
    if args:
        target = Path(args[0])
        if not target.is_absolute():
            target = PROJECT_ROOT / target
    else:
        target = BACKEND_DIR

    print(f"\nScanning: {target}")

    # Scan Python files
    print("\nScanning Python files...")
    if target.is_file():
        python_files = {str(target.relative_to(PROJECT_ROOT)): target.read_text()}
    else:
        python_files = scan_python_files(target)
    print(f"  Found {len(python_files)} Python files")

    # Scan TypeScript files
    print("Scanning TypeScript files...")
    if "frontend" in str(target) or target == PROJECT_ROOT:
        typescript_files = scan_typescript_files(FRONTEND_DIR)
    else:
        typescript_files = {}
    print(f"  Found {len(typescript_files)} TypeScript files")

    # Analyze with Claude
    analysis = analyze_bugs(python_files, typescript_files)

    if "error" in analysis:
        print(f"\nError: {analysis['error']}")
        return 1

    # Save report
    report_file = save_bug_report(analysis, python_files, typescript_files)

    # Print summary
    print("\n" + "=" * 60)
    print("BUG PREDICTION COMPLETE")
    print("=" * 60)

    if "summary" in analysis:
        summary = analysis["summary"]
        print(f"Risk Score: {summary.get('risk_score', 'N/A')}/100")
        print(f"Potential Bugs: {summary.get('potential_bugs', 0)}")
        print(f"  Critical: {summary.get('critical', 0)}")
        print(f"  High: {summary.get('high', 0)}")
        print(f"  Medium: {summary.get('medium', 0)}")
        print(f"  Low: {summary.get('low', 0)}")

    print(f"\nFull report: {report_file}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
