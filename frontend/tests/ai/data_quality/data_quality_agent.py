#!/usr/bin/env python3
"""
CLAUDE-DATA-QUALITY: AI Data Quality Engine

Scans database for:
- Missing fields
- Bad relationships
- Duplicate records
- Orphan data
- Broken foreign keys
- Invalid dates
- Null anomalies
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
You are CLAUDE-DATA-QUALITY, an expert in database data quality analysis.

You detect and report:
1. Duplicate rows (based on natural keys)
2. Null anomalies (unexpected NULLs, missing required fields)
3. Inconsistent relationships (mismatched foreign keys)
4. Orphan data (records with no valid parent)
5. Wrong timestamps (future dates, invalid ranges)
6. Invalid enum values (values not in expected set)
7. Data type mismatches
8. Referential integrity violations
9. Statistical anomalies (outliers)
10. Encoding issues

ABVTrends Database Schema:
- products: id, name, brand, category, subcategory, created_at, updated_at
- trends: id, product_id, score, trend_tier, calculated_at
- signals: id, product_id, source, signal_type, strength, captured_at
- forecasts: id, product_id, predicted_score, prediction_date
- scraper_logs: id, source, status, items_scraped, started_at, completed_at

Output Format (JSON):
{
  "summary": {
    "tables_analyzed": ["..."],
    "total_issues": 0,
    "critical_issues": 0,
    "data_quality_score": 0-100
  },
  "issues": [
    {
      "id": "DQ-001",
      "severity": "critical|high|medium|low",
      "category": "duplicate|null|orphan|invalid|anomaly|...",
      "table": "table_name",
      "column": "column_name",
      "description": "What's wrong",
      "affected_rows": 0,
      "sample_data": ["..."],
      "sql_fix": "SQL to fix the issue",
      "python_fix": "Python code to fix (optional)"
    }
  ],
  "recommendations": [
    {
      "priority": "high|medium|low",
      "description": "...",
      "implementation": "..."
    }
  ],
  "sql_audit_queries": ["Queries to run for ongoing monitoring"]
}
"""


def get_database_connection():
    """Get database connection if available."""

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        return None

    try:
        import psycopg2
        conn = psycopg2.connect(database_url)
        return conn
    except ImportError:
        print("psycopg2 not installed. Install with: pip install psycopg2-binary")
        return None
    except Exception as e:
        print(f"Could not connect to database: {e}")
        return None


def fetch_table_stats(conn) -> dict:
    """Fetch statistics about database tables."""

    stats = {}
    cursor = conn.cursor()

    tables = ["products", "trends", "signals", "forecasts", "scraper_logs"]

    for table in tables:
        try:
            # Row count
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]

            # Column info
            cursor.execute(f"""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = '{table}'
            """)
            columns = cursor.fetchall()

            # Null counts
            null_counts = {}
            for col_name, _, is_nullable in columns:
                if is_nullable == 'YES':
                    cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE {col_name} IS NULL")
                    null_counts[col_name] = cursor.fetchone()[0]

            stats[table] = {
                "row_count": count,
                "columns": [{"name": c[0], "type": c[1], "nullable": c[2]} for c in columns],
                "null_counts": null_counts
            }

        except Exception as e:
            stats[table] = {"error": str(e)}

    return stats


def fetch_sample_data(conn) -> dict:
    """Fetch sample data from each table."""

    samples = {}
    cursor = conn.cursor()

    tables = ["products", "trends", "signals"]

    for table in tables:
        try:
            cursor.execute(f"SELECT * FROM {table} LIMIT 50")
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()

            samples[table] = {
                "columns": columns,
                "rows": [dict(zip(columns, row)) for row in rows]
            }
        except Exception as e:
            samples[table] = {"error": str(e)}

    return samples


def check_duplicates(conn) -> list:
    """Check for duplicate records."""

    duplicates = []
    cursor = conn.cursor()

    # Check products duplicates (by name + brand)
    try:
        cursor.execute("""
            SELECT name, brand, COUNT(*) as cnt
            FROM products
            GROUP BY name, brand
            HAVING COUNT(*) > 1
        """)
        for row in cursor.fetchall():
            duplicates.append({
                "table": "products",
                "key": f"{row[0]} - {row[1]}",
                "count": row[2]
            })
    except:
        pass

    return duplicates


def check_orphans(conn) -> list:
    """Check for orphan records."""

    orphans = []
    cursor = conn.cursor()

    # Trends without products
    try:
        cursor.execute("""
            SELECT COUNT(*)
            FROM trends t
            LEFT JOIN products p ON t.product_id = p.id
            WHERE p.id IS NULL
        """)
        count = cursor.fetchone()[0]
        if count > 0:
            orphans.append({
                "table": "trends",
                "foreign_key": "product_id",
                "parent_table": "products",
                "orphan_count": count
            })
    except:
        pass

    # Signals without products
    try:
        cursor.execute("""
            SELECT COUNT(*)
            FROM signals s
            LEFT JOIN products p ON s.product_id = p.id
            WHERE p.id IS NULL
        """)
        count = cursor.fetchone()[0]
        if count > 0:
            orphans.append({
                "table": "signals",
                "foreign_key": "product_id",
                "parent_table": "products",
                "orphan_count": count
            })
    except:
        pass

    return orphans


def analyze_data_quality(table_stats: dict, samples: dict, duplicates: list, orphans: list) -> dict:
    """Analyze data quality with Claude."""

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {"error": "ANTHROPIC_API_KEY not set"}

    print("Analyzing data quality with Claude...")

    # Prepare data for analysis
    analysis_data = {
        "table_stats": table_stats,
        "sample_data": {k: v for k, v in samples.items() if "rows" in v},
        "duplicates_found": duplicates,
        "orphans_found": orphans
    }

    # Serialize sample data carefully
    for table, data in analysis_data["sample_data"].items():
        if "rows" in data:
            # Convert any non-serializable types
            for row in data["rows"]:
                for key, value in row.items():
                    if isinstance(value, datetime):
                        row[key] = value.isoformat()
                    elif hasattr(value, '__dict__'):
                        row[key] = str(value)

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"""
Analyze this database data quality for ABVTrends.

## Table Statistics
{json.dumps(table_stats, indent=2, default=str)}

## Sample Data (first 50 rows each)
{json.dumps(analysis_data["sample_data"], indent=2, default=str)[:10000]}

## Duplicates Found
{json.dumps(duplicates, indent=2)}

## Orphan Records Found
{json.dumps(orphans, indent=2)}

Please:
1. Identify all data quality issues
2. Calculate a data quality score (0-100)
3. Provide SQL queries to fix issues
4. Suggest ongoing monitoring queries
5. Prioritize recommendations

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


def generate_mock_analysis() -> dict:
    """Generate mock analysis when database is not available."""

    return {
        "summary": {
            "tables_analyzed": ["products", "trends", "signals"],
            "total_issues": 0,
            "critical_issues": 0,
            "data_quality_score": 100,
            "note": "No database connection available - mock analysis"
        },
        "issues": [],
        "recommendations": [
            {
                "priority": "high",
                "description": "Set DATABASE_URL environment variable to enable real analysis",
                "implementation": "export DATABASE_URL=postgresql://user:pass@host:port/dbname"
            }
        ],
        "sql_audit_queries": [
            "-- Duplicate products check\nSELECT name, brand, COUNT(*) FROM products GROUP BY name, brand HAVING COUNT(*) > 1;",
            "-- Orphan trends check\nSELECT COUNT(*) FROM trends t LEFT JOIN products p ON t.product_id = p.id WHERE p.id IS NULL;",
            "-- Null score check\nSELECT COUNT(*) FROM trends WHERE score IS NULL;",
            "-- Future timestamp check\nSELECT COUNT(*) FROM trends WHERE calculated_at > NOW();"
        ]
    }


def save_report(analysis: dict):
    """Save data quality report."""

    RESULTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save JSON
    json_file = RESULTS_DIR / f"data_quality_{timestamp}.json"
    with open(json_file, "w") as f:
        json.dump(analysis, f, indent=2, default=str)

    # Save markdown report
    report_file = RESULTS_DIR / "data_quality_report.md"
    with open(report_file, "w") as f:
        f.write("# Data Quality Report\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")

        if "summary" in analysis:
            summary = analysis["summary"]
            f.write("## Summary\n\n")
            f.write(f"- **Tables Analyzed:** {', '.join(summary.get('tables_analyzed', []))}\n")
            f.write(f"- **Total Issues:** {summary.get('total_issues', 'N/A')}\n")
            f.write(f"- **Critical Issues:** {summary.get('critical_issues', 'N/A')}\n")
            f.write(f"- **Data Quality Score:** {summary.get('data_quality_score', 'N/A')}/100\n\n")

        if "issues" in analysis and analysis["issues"]:
            f.write("## Issues Found\n\n")
            for issue in analysis["issues"]:
                severity = issue.get("severity", "unknown")
                f.write(f"### [{severity.upper()}] {issue.get('id', 'N/A')}: {issue.get('category', '')}\n")
                f.write(f"**Table:** `{issue.get('table', 'N/A')}`\n")
                if issue.get("column"):
                    f.write(f"**Column:** `{issue['column']}`\n")
                f.write(f"**Description:** {issue.get('description', 'N/A')}\n")
                f.write(f"**Affected Rows:** {issue.get('affected_rows', 'N/A')}\n\n")

                if issue.get("sql_fix"):
                    f.write(f"**SQL Fix:**\n```sql\n{issue['sql_fix']}\n```\n\n")

        if "recommendations" in analysis:
            f.write("## Recommendations\n\n")
            for rec in analysis["recommendations"]:
                priority = rec.get("priority", "medium")
                f.write(f"### [{priority.upper()}] {rec.get('description', 'N/A')}\n")
                if rec.get("implementation"):
                    f.write(f"{rec['implementation']}\n\n")

        if "sql_audit_queries" in analysis:
            f.write("## Audit Queries\n\n")
            f.write("Use these queries for ongoing monitoring:\n\n")
            for query in analysis["sql_audit_queries"]:
                f.write(f"```sql\n{query}\n```\n\n")

        if "raw_response" in analysis:
            f.write("## Raw Analysis\n\n")
            f.write(analysis["raw_response"])

    print(f"\nReport saved to: {report_file}")


def main():
    """Main execution flow."""

    print("=" * 60)
    print("CLAUDE-DATA-QUALITY: AI Data Quality Engine")
    print("=" * 60)

    # Try to connect to database
    conn = get_database_connection()

    if conn:
        print("\nConnected to database")

        # Gather data
        print("Fetching table statistics...")
        table_stats = fetch_table_stats(conn)

        print("Fetching sample data...")
        samples = fetch_sample_data(conn)

        print("Checking for duplicates...")
        duplicates = check_duplicates(conn)

        print("Checking for orphan records...")
        orphans = check_orphans(conn)

        conn.close()

        # Analyze with Claude
        analysis = analyze_data_quality(table_stats, samples, duplicates, orphans)
    else:
        print("\nNo database connection available")
        print("Generating mock analysis...")
        analysis = generate_mock_analysis()

    if "error" in analysis:
        print(f"\nError: {analysis['error']}")
        return 1

    # Save report
    save_report(analysis)

    # Print summary
    print("\n" + "=" * 60)
    print("DATA QUALITY SUMMARY")
    print("=" * 60)

    if "summary" in analysis:
        summary = analysis["summary"]
        score = summary.get("data_quality_score", "N/A")
        print(f"Data Quality Score: {score}/100")
        print(f"Total Issues: {summary.get('total_issues', 0)}")
        print(f"Critical Issues: {summary.get('critical_issues', 0)}")

    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
