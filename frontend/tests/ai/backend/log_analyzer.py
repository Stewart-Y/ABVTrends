#!/usr/bin/env python3
"""
CLAUDE-LOG-ANALYZER: AI Error Log Analyzer

Reads backend logs, identifies root causes, and suggests code fixes.
Prioritizes issues by severity and impact.
"""

import os
import sys
import re
import json
from datetime import datetime, timedelta
from pathlib import Path
from collections import Counter

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
You are CLAUDE-LOG-ANALYZER, an expert in analyzing application logs and debugging.

You analyze:
1. Python error logs and tracebacks
2. FastAPI request/response logs
3. SQLAlchemy query logs
4. Application warnings and errors
5. Performance-related log entries

Your responsibilities:
1. Identify root causes of errors
2. Categorize issues by type and severity
3. Find patterns in recurring errors
4. Suggest specific code fixes
5. Prioritize issues by impact

Log Entry Categories:
- ERROR: Application errors, exceptions
- WARNING: Potential issues, deprecations
- SLOW: Performance warnings
- SECURITY: Authentication, authorization issues
- DATABASE: Query errors, connection issues

Severity Levels:
- CRITICAL: Service down, data corruption risk
- HIGH: Feature broken, user impact
- MEDIUM: Degraded functionality
- LOW: Minor issues, cosmetic

Output Format (JSON):
{
  "summary": {
    "total_entries": 0,
    "error_count": 0,
    "warning_count": 0,
    "time_range": "..."
  },
  "issues": [
    {
      "id": "ISSUE-001",
      "severity": "critical|high|medium|low",
      "category": "error|warning|performance|security|database",
      "title": "Brief description",
      "description": "Detailed explanation",
      "occurrences": 0,
      "first_seen": "timestamp",
      "last_seen": "timestamp",
      "root_cause": "Analysis of why this happens",
      "affected_file": "file path if identifiable",
      "suggested_fix": {
        "description": "What to do",
        "code": "Code snippet if applicable"
      }
    }
  ],
  "patterns": [
    {
      "pattern": "Description of recurring pattern",
      "frequency": "How often",
      "recommendation": "What to do about it"
    }
  ],
  "recommendations": [
    {
      "priority": "high|medium|low",
      "category": "...",
      "description": "..."
    }
  ]
}
"""


def find_log_files() -> list[Path]:
    """Find available log files."""

    log_locations = [
        BACKEND_DIR / "app.log",
        BACKEND_DIR / "logs" / "app.log",
        BACKEND_DIR / "logs" / "error.log",
        RESULTS_DIR / "backend_error.log",
        Path("/var/log/abvtrends/app.log"),
        Path("/tmp/abvtrends.log"),
    ]

    found = []
    for path in log_locations:
        if path.exists():
            found.append(path)

    return found


def parse_log_entries(log_content: str) -> list[dict]:
    """Parse log content into structured entries."""

    entries = []

    # Common log patterns
    patterns = [
        # Standard Python logging format
        r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:,\d{3})?)\s+-\s+(\w+)\s+-\s+(.*?)(?=\d{4}-\d{2}-\d{2}|\Z)',
        # FastAPI/uvicorn format
        r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+(\w+):\s+(.*?)(?=\d{4}-\d{2}-\d{2}|\Z)',
        # Simple format
        r'\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\]\s+\[(\w+)\]\s+(.*?)(?=\[|\Z)',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, log_content, re.DOTALL)
        if matches:
            for timestamp, level, message in matches:
                entries.append({
                    "timestamp": timestamp.strip(),
                    "level": level.upper(),
                    "message": message.strip()
                })
            break

    # If no structured format found, look for errors/tracebacks
    if not entries:
        # Find Python tracebacks
        traceback_pattern = r'Traceback \(most recent call last\):.*?(?=\n\n|\Z)'
        for match in re.finditer(traceback_pattern, log_content, re.DOTALL):
            entries.append({
                "timestamp": "unknown",
                "level": "ERROR",
                "message": match.group()
            })

        # Find error lines
        error_pattern = r'(?:ERROR|Error|error):?\s*(.*)'
        for match in re.finditer(error_pattern, log_content):
            entries.append({
                "timestamp": "unknown",
                "level": "ERROR",
                "message": match.group(1)
            })

    return entries


def aggregate_entries(entries: list[dict]) -> dict:
    """Aggregate and summarize log entries."""

    summary = {
        "total": len(entries),
        "by_level": Counter(e["level"] for e in entries),
        "error_messages": Counter(),
        "warning_messages": Counter()
    }

    for entry in entries:
        # Normalize message for grouping
        msg = entry["message"][:200]  # First 200 chars
        msg = re.sub(r'\d+', 'N', msg)  # Replace numbers
        msg = re.sub(r'0x[a-fA-F0-9]+', 'ADDR', msg)  # Replace memory addresses

        if entry["level"] in ["ERROR", "CRITICAL"]:
            summary["error_messages"][msg] += 1
        elif entry["level"] == "WARNING":
            summary["warning_messages"][msg] += 1

    return summary


def analyze_logs(log_content: str) -> dict:
    """Analyze logs with Claude."""

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {"error": "ANTHROPIC_API_KEY not set"}

    print("Parsing log entries...")
    entries = parse_log_entries(log_content)
    summary = aggregate_entries(entries)

    print(f"  Total entries: {summary['total']}")
    print(f"  Errors: {summary['by_level'].get('ERROR', 0)}")
    print(f"  Warnings: {summary['by_level'].get('WARNING', 0)}")
    print(f"  Unique error patterns: {len(summary['error_messages'])}")

    # Prepare log sample for Claude (truncate if too long)
    log_sample = log_content[:15000] if len(log_content) > 15000 else log_content

    # Get most common errors
    top_errors = summary["error_messages"].most_common(10)
    top_warnings = summary["warning_messages"].most_common(10)

    print("\nSending to Claude for analysis...")

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"""
Analyze these backend logs from ABVTrends and identify issues.

## Log Statistics
- Total entries: {summary['total']}
- Errors: {summary['by_level'].get('ERROR', 0)}
- Warnings: {summary['by_level'].get('WARNING', 0)}
- Critical: {summary['by_level'].get('CRITICAL', 0)}

## Most Common Errors (by frequency)
{json.dumps(top_errors, indent=2)}

## Most Common Warnings (by frequency)
{json.dumps(top_warnings, indent=2)}

## Log Sample
```
{log_sample}
```

Please:
1. Identify all issues and their root causes
2. Categorize by severity and type
3. Find patterns in recurring errors
4. Suggest specific code fixes
5. Prioritize what to fix first

Return your analysis as JSON.
"""
                }
            ]
        )

        content = response.content[0].text

        # Parse JSON response
        try:
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                result = json.loads(json_match.group())
                result["raw_stats"] = {
                    "total_entries": summary["total"],
                    "by_level": dict(summary["by_level"]),
                    "unique_errors": len(summary["error_messages"])
                }
                return result
        except json.JSONDecodeError:
            pass

        return {"raw_response": content}

    except Exception as e:
        return {"error": str(e)}


def save_report(analysis: dict):
    """Save log analysis report."""

    RESULTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save JSON
    json_file = RESULTS_DIR / f"log_analysis_{timestamp}.json"
    with open(json_file, "w") as f:
        json.dump(analysis, f, indent=2)

    # Save markdown report
    report_file = RESULTS_DIR / "log_analysis.md"
    with open(report_file, "w") as f:
        f.write(f"# Log Analysis Report\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")

        if "summary" in analysis:
            f.write("## Summary\n\n")
            summary = analysis["summary"]
            f.write(f"- **Total Entries:** {summary.get('total_entries', 'N/A')}\n")
            f.write(f"- **Errors:** {summary.get('error_count', 'N/A')}\n")
            f.write(f"- **Warnings:** {summary.get('warning_count', 'N/A')}\n")
            f.write(f"- **Time Range:** {summary.get('time_range', 'N/A')}\n\n")

        if "issues" in analysis:
            f.write("## Issues\n\n")

            # Group by severity
            issues_by_severity = {}
            for issue in analysis["issues"]:
                severity = issue.get("severity", "unknown")
                if severity not in issues_by_severity:
                    issues_by_severity[severity] = []
                issues_by_severity[severity].append(issue)

            for severity in ["critical", "high", "medium", "low"]:
                if severity in issues_by_severity:
                    f.write(f"### {severity.upper()} Severity\n\n")
                    for issue in issues_by_severity[severity]:
                        f.write(f"#### {issue.get('id', 'N/A')}: {issue.get('title', 'Unknown')}\n")
                        f.write(f"**Category:** {issue.get('category', 'N/A')}\n")
                        f.write(f"**Occurrences:** {issue.get('occurrences', 'N/A')}\n\n")
                        f.write(f"{issue.get('description', 'N/A')}\n\n")

                        if issue.get("root_cause"):
                            f.write(f"**Root Cause:** {issue['root_cause']}\n\n")

                        if issue.get("suggested_fix"):
                            fix = issue["suggested_fix"]
                            f.write(f"**Fix:** {fix.get('description', 'N/A')}\n")
                            if fix.get("code"):
                                f.write(f"```python\n{fix['code']}\n```\n")
                        f.write("\n---\n\n")

        if "patterns" in analysis:
            f.write("## Recurring Patterns\n\n")
            for pattern in analysis["patterns"]:
                f.write(f"- **{pattern.get('pattern', 'N/A')}**\n")
                f.write(f"  - Frequency: {pattern.get('frequency', 'N/A')}\n")
                f.write(f"  - Recommendation: {pattern.get('recommendation', 'N/A')}\n\n")

        if "recommendations" in analysis:
            f.write("## Recommendations\n\n")
            for rec in analysis["recommendations"]:
                priority = rec.get("priority", "medium")
                f.write(f"### [{priority.upper()}] {rec.get('category', 'General')}\n")
                f.write(f"{rec.get('description', 'N/A')}\n\n")

        if "raw_response" in analysis:
            f.write("## Raw Analysis\n\n")
            f.write(analysis["raw_response"])

    print(f"\nReport saved to: {report_file}")


def main():
    """Main execution flow."""

    print("=" * 60)
    print("CLAUDE-LOG-ANALYZER: AI Error Log Analyzer")
    print("=" * 60)

    # Find log files
    log_files = find_log_files()

    # Check for command line argument
    if len(sys.argv) > 1:
        log_path = Path(sys.argv[1])
        if log_path.exists():
            log_files = [log_path]
        else:
            print(f"File not found: {log_path}")
            return 1

    if not log_files:
        print("\nNo log files found. Checking for stdin...")

        # Try reading from stdin
        if not sys.stdin.isatty():
            log_content = sys.stdin.read()
        else:
            print("\nUsage: python log_analyzer.py [log_file_path]")
            print("   or: cat app.log | python log_analyzer.py")
            print("\nSearched locations:")
            print(f"  - {BACKEND_DIR / 'app.log'}")
            print(f"  - {BACKEND_DIR / 'logs/'}")
            print(f"  - {RESULTS_DIR / 'backend_error.log'}")
            return 1
    else:
        print(f"\nFound {len(log_files)} log file(s):")
        for f in log_files:
            print(f"  - {f}")

        # Read all log files
        log_content = ""
        for log_file in log_files:
            try:
                content = log_file.read_text()
                log_content += f"\n=== {log_file} ===\n{content}\n"
            except Exception as e:
                print(f"  Error reading {log_file}: {e}")

    if not log_content.strip():
        print("No log content to analyze")
        return 1

    # Analyze logs
    analysis = analyze_logs(log_content)

    if "error" in analysis:
        print(f"\nError: {analysis['error']}")
        return 1

    # Save report
    save_report(analysis)

    # Print summary
    print("\n" + "=" * 60)
    print("LOG ANALYSIS SUMMARY")
    print("=" * 60)

    if "issues" in analysis:
        issues = analysis["issues"]
        critical = len([i for i in issues if i.get("severity") == "critical"])
        high = len([i for i in issues if i.get("severity") == "high"])
        print(f"Issues found: {len(issues)}")
        print(f"  Critical: {critical}")
        print(f"  High: {high}")

    if "patterns" in analysis:
        print(f"Recurring patterns: {len(analysis['patterns'])}")

    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
