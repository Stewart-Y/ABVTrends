#!/usr/bin/env python3
"""
CLAUDE-PERF-DOCTOR: AI Performance Hotspot Detector

Analyzes Python profiling output, slow queries, and logs to identify
performance bottlenecks and suggest optimizations.
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
You are CLAUDE-PERF-DOCTOR, an expert in Python performance optimization.

You analyze:
1. Python profiling output (cProfile, py-spy, yappi)
2. Slow database queries (SQLAlchemy logs)
3. Application logs with timing data
4. Endpoint response times
5. Memory usage patterns

You identify:
1. Performance hotspots (slow functions)
2. Missing database indexes
3. N+1 ORM query problems
4. Blocking I/O issues
5. Inefficient loops and algorithms
6. Memory leaks
7. Async/await improvements

ABVTrends Performance Context:
- FastAPI with async endpoints
- SQLAlchemy 2.0 async ORM
- PostgreSQL database
- Heavy data processing for trend scoring
- Web scraping operations

Output Format (JSON):
{
  "summary": "Overall performance assessment",
  "hotspots": [
    {
      "location": "file:function:line",
      "issue": "Description of issue",
      "impact": "high|medium|low",
      "suggestion": "How to fix",
      "code_fix": "Optional code snippet"
    }
  ],
  "database_issues": [
    {
      "query": "The problematic query",
      "issue": "Description",
      "suggestion": "Index or query fix"
    }
  ],
  "recommendations": [
    {
      "category": "caching|indexing|async|algorithm|...",
      "description": "...",
      "priority": "high|medium|low",
      "implementation": "..."
    }
  ],
  "metrics": {
    "estimated_improvement": "...",
    "areas_to_monitor": ["..."]
  }
}
"""


def read_profiler_output() -> str:
    """Read profiler output if available."""

    profiler_files = [
        RESULTS_DIR / "profiler_output.txt",
        RESULTS_DIR / "profile.txt",
        BACKEND_DIR / "profile_output.txt",
    ]

    for file in profiler_files:
        if file.exists():
            return file.read_text()

    return ""


def read_slow_query_log() -> str:
    """Read slow query logs if available."""

    log_files = [
        RESULTS_DIR / "slow_queries.log",
        BACKEND_DIR / "slow_queries.log",
        BACKEND_DIR / "app.log",
    ]

    slow_queries = []

    for file in log_files:
        if file.exists():
            try:
                content = file.read_text()
                # Extract SQL queries and timing
                sql_pattern = r'(SELECT|INSERT|UPDATE|DELETE).*?(?=\n\n|\Z)'
                time_pattern = r'Time:\s*([\d.]+)\s*(?:ms|s)'

                for match in re.finditer(sql_pattern, content, re.DOTALL | re.IGNORECASE):
                    slow_queries.append(match.group())

            except Exception as e:
                print(f"Error reading {file}: {e}")

    return "\n---\n".join(slow_queries) if slow_queries else ""


def analyze_code_for_performance() -> dict:
    """Static analysis of code for performance issues."""

    issues = []

    # Patterns that often indicate performance problems
    patterns = [
        (r'for\s+\w+\s+in\s+\w+\.query\.all\(\)', "N+1 query pattern"),
        (r'\.all\(\)\s*\)', "Loading all records into memory"),
        (r'time\.sleep\(', "Blocking sleep in async context"),
        (r'requests\.(get|post)\(', "Sync HTTP in async code"),
        (r'open\([^)]+\)\.read\(\)', "Reading entire file into memory"),
        (r'for.*in.*for.*in', "Nested loops (O(n^2) potential)"),
        (r'\.execute\([^)]*%', "String interpolation in SQL (risk + perf)"),
    ]

    services_dir = BACKEND_DIR / "app" / "services"
    api_dir = BACKEND_DIR / "app" / "api"

    for search_dir in [services_dir, api_dir]:
        if search_dir.exists():
            for file in search_dir.rglob("*.py"):
                try:
                    content = file.read_text()
                    for pattern, issue_type in patterns:
                        for match in re.finditer(pattern, content):
                            line_num = content[:match.start()].count('\n') + 1
                            issues.append({
                                "file": str(file.relative_to(BACKEND_DIR)),
                                "line": line_num,
                                "pattern": pattern,
                                "issue": issue_type,
                                "code": match.group()[:100]
                            })
                except:
                    continue

    return {"static_analysis_issues": issues}


def get_endpoint_metrics() -> dict:
    """Get endpoint response time metrics if available."""

    metrics_file = RESULTS_DIR / "endpoint_metrics.json"
    if metrics_file.exists():
        try:
            return json.load(open(metrics_file))
        except:
            pass

    return {}


def run_performance_analysis() -> dict:
    """Run comprehensive performance analysis."""

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {"error": "ANTHROPIC_API_KEY not set"}

    print("Gathering performance data...")

    # Gather all available data
    profiler_output = read_profiler_output()
    slow_queries = read_slow_query_log()
    static_issues = analyze_code_for_performance()
    endpoint_metrics = get_endpoint_metrics()

    print(f"  Profiler data: {'Available' if profiler_output else 'Not available'}")
    print(f"  Slow queries: {'Found' if slow_queries else 'None found'}")
    print(f"  Static issues: {len(static_issues.get('static_analysis_issues', []))}")
    print(f"  Endpoint metrics: {'Available' if endpoint_metrics else 'Not available'}")

    # Read some key service files for context
    key_files = {}
    key_paths = [
        BACKEND_DIR / "app" / "services" / "trend_engine.py",
        BACKEND_DIR / "app" / "services" / "signal_processor.py",
        BACKEND_DIR / "app" / "api" / "v1" / "trends.py",
    ]

    for path in key_paths:
        if path.exists():
            try:
                key_files[path.name] = path.read_text()[:3000]  # First 3000 chars
            except:
                pass

    # Build context
    context = "## Performance Analysis Request\n\n"

    if profiler_output:
        context += f"### Profiler Output\n```\n{profiler_output[:5000]}\n```\n\n"

    if slow_queries:
        context += f"### Slow Queries\n```sql\n{slow_queries[:3000]}\n```\n\n"

    if static_issues.get("static_analysis_issues"):
        context += f"### Static Analysis Issues\n```json\n{json.dumps(static_issues, indent=2)}\n```\n\n"

    if endpoint_metrics:
        context += f"### Endpoint Metrics\n```json\n{json.dumps(endpoint_metrics, indent=2)}\n```\n\n"

    if key_files:
        context += "### Key Source Files\n"
        for name, content in key_files.items():
            context += f"#### {name}\n```python\n{content}\n```\n\n"

    print("\nSending to Claude for performance analysis...")

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"""
Analyze the following performance data for ABVTrends backend and provide optimization recommendations.

{context}

Please identify:
1. Performance hotspots
2. Database optimization opportunities
3. Code improvements
4. Caching strategies
5. Async optimization opportunities

Return your analysis as JSON.
"""
                }
            ]
        )

        content = response.content[0].text

        # Try to parse JSON
        try:
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

        return {"raw_response": content}

    except Exception as e:
        return {"error": str(e)}


def save_report(analysis: dict):
    """Save performance analysis report."""

    RESULTS_DIR.mkdir(exist_ok=True)
    SUGGESTIONS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save JSON
    json_file = RESULTS_DIR / f"performance_analysis_{timestamp}.json"
    with open(json_file, "w") as f:
        json.dump(analysis, f, indent=2)

    # Save markdown report
    report_file = RESULTS_DIR / "performance_report.md"
    with open(report_file, "w") as f:
        f.write(f"# Performance Analysis Report\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")

        if "summary" in analysis:
            f.write("## Summary\n")
            f.write(analysis["summary"])
            f.write("\n\n")

        if "hotspots" in analysis:
            f.write("## Performance Hotspots\n\n")
            for hotspot in analysis["hotspots"]:
                impact = hotspot.get("impact", "unknown")
                f.write(f"### [{impact.upper()}] {hotspot.get('location', 'Unknown')}\n")
                f.write(f"**Issue:** {hotspot.get('issue', 'N/A')}\n\n")
                f.write(f"**Suggestion:** {hotspot.get('suggestion', 'N/A')}\n\n")
                if hotspot.get("code_fix"):
                    f.write(f"```python\n{hotspot['code_fix']}\n```\n\n")

        if "database_issues" in analysis:
            f.write("## Database Issues\n\n")
            for issue in analysis["database_issues"]:
                f.write(f"### Query Issue\n")
                f.write(f"```sql\n{issue.get('query', 'N/A')}\n```\n")
                f.write(f"**Issue:** {issue.get('issue', 'N/A')}\n\n")
                f.write(f"**Suggestion:** {issue.get('suggestion', 'N/A')}\n\n")

        if "recommendations" in analysis:
            f.write("## Recommendations\n\n")
            for rec in analysis["recommendations"]:
                priority = rec.get("priority", "medium")
                f.write(f"### [{priority.upper()}] {rec.get('category', 'General')}\n")
                f.write(f"{rec.get('description', 'N/A')}\n\n")
                if rec.get("implementation"):
                    f.write(f"**Implementation:**\n{rec['implementation']}\n\n")

        if "metrics" in analysis:
            f.write("## Metrics & Estimates\n\n")
            f.write(f"**Estimated Improvement:** {analysis['metrics'].get('estimated_improvement', 'N/A')}\n\n")
            if analysis['metrics'].get('areas_to_monitor'):
                f.write("**Areas to Monitor:**\n")
                for area in analysis['metrics']['areas_to_monitor']:
                    f.write(f"- {area}\n")

        if "raw_response" in analysis:
            f.write("## Raw Analysis\n\n")
            f.write(analysis["raw_response"])

    print(f"\nReport saved to: {report_file}")


def main():
    """Main execution flow."""

    print("=" * 60)
    print("CLAUDE-PERF-DOCTOR: Performance Hotspot Detector")
    print("=" * 60)

    # Run analysis
    analysis = run_performance_analysis()

    if "error" in analysis:
        print(f"\nError: {analysis['error']}")
        return 1

    # Save report
    save_report(analysis)

    # Print summary
    print("\n" + "=" * 60)
    print("PERFORMANCE ANALYSIS SUMMARY")
    print("=" * 60)

    if "summary" in analysis:
        print(analysis["summary"])

    if "hotspots" in analysis:
        high = len([h for h in analysis["hotspots"] if h.get("impact") == "high"])
        print(f"\nHotspots: {len(analysis['hotspots'])} ({high} high impact)")

    if "recommendations" in analysis:
        high_priority = len([r for r in analysis["recommendations"] if r.get("priority") == "high"])
        print(f"Recommendations: {len(analysis['recommendations'])} ({high_priority} high priority)")

    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
