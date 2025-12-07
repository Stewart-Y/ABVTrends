#!/usr/bin/env python3
"""
CLAUDE-MODEL-AUDITOR: AI SQLAlchemy Model Auditor + Migrator

Compares SQLAlchemy models vs database schema, detects mismatches,
and generates Alembic migration code to fix breaking schema differences.
"""

import os
import sys
import re
import json
import subprocess
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
You are CLAUDE-MODEL-AUDITOR, an expert in SQLAlchemy ORM and database migrations.

You analyze:
1. SQLAlchemy model definitions
2. Alembic migration history
3. PostgreSQL database schema dumps
4. Current vs expected state

Your responsibilities:
1. Detect schema mismatches between models and database
2. Identify missing columns, tables, indexes, constraints
3. Find nullable/PK/FK/index issues
4. Generate Alembic migration code to fix issues
5. Suggest model repairs if needed
6. Warn about potentially breaking changes

ABVTrends Schema includes:
- products: Product catalog with metadata
- trends: Trend scores and tier assignments
- signals: Individual trend signals from various sources
- forecasts: AI-generated trend predictions
- scraper_logs: Web scraping activity logs

Output Format (JSON):
{
  "summary": "Overall health assessment",
  "mismatches": [
    {
      "type": "missing_column|extra_column|type_mismatch|missing_index|...",
      "table": "table_name",
      "column": "column_name",
      "model_definition": "...",
      "database_definition": "...",
      "severity": "critical|high|medium|low",
      "fix": "description of fix"
    }
  ],
  "migration_code": "# Alembic migration code...",
  "model_fixes": [
    {
      "file": "...",
      "changes": "..."
    }
  ],
  "recommendations": ["..."]
}
"""


def read_models() -> dict[str, str]:
    """Read all SQLAlchemy model files."""

    models = {}
    models_dir = BACKEND_DIR / "app" / "models"

    if models_dir.exists():
        for file in models_dir.glob("*.py"):
            try:
                content = file.read_text()
                models[file.name] = content
            except:
                continue

    # Also check for models in other locations
    alt_locations = [
        BACKEND_DIR / "app" / "db" / "models.py",
        BACKEND_DIR / "models.py",
    ]

    for path in alt_locations:
        if path.exists():
            try:
                models[path.name] = path.read_text()
            except:
                continue

    return models


def read_migrations() -> list[dict]:
    """Read Alembic migration files."""

    migrations = []
    versions_dir = BACKEND_DIR / "alembic" / "versions"

    if versions_dir.exists():
        for file in sorted(versions_dir.glob("*.py")):
            try:
                content = file.read_text()
                migrations.append({
                    "filename": file.name,
                    "content": content[:2000]  # First 2000 chars
                })
            except:
                continue

    return migrations


def get_database_schema() -> str:
    """Get database schema via pg_dump or manual inspection."""

    # First check if we have a cached schema dump
    schema_file = RESULTS_DIR / "db_schema_dump.txt"
    if schema_file.exists():
        return schema_file.read_text()

    # Try to get schema from environment
    database_url = os.environ.get("DATABASE_URL", "")

    if database_url:
        try:
            # Parse database URL
            # Format: postgresql://user:pass@host:port/dbname
            match = re.match(
                r'postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)',
                database_url
            )

            if match:
                user, password, host, port, dbname = match.groups()

                # Try pg_dump
                result = subprocess.run(
                    [
                        "pg_dump",
                        "-h", host,
                        "-p", port,
                        "-U", user,
                        "-d", dbname,
                        "--schema-only",
                        "--no-owner",
                        "--no-privileges"
                    ],
                    capture_output=True,
                    text=True,
                    env={**os.environ, "PGPASSWORD": password},
                    timeout=30
                )

                if result.returncode == 0:
                    return result.stdout

        except Exception as e:
            print(f"Could not dump schema: {e}")

    # Return placeholder if we couldn't get schema
    return """
-- No database schema available
-- To provide schema, either:
-- 1. Set DATABASE_URL environment variable
-- 2. Create tests/ai/results/db_schema_dump.txt with pg_dump output
--
-- Example: pg_dump -h localhost -U user -d dbname --schema-only > db_schema_dump.txt
"""


def run_model_audit() -> dict:
    """Run comprehensive model audit with Claude."""

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {"error": "ANTHROPIC_API_KEY not set"}

    print("Gathering model and schema information...")

    # Gather all information
    models = read_models()
    migrations = read_migrations()
    db_schema = get_database_schema()

    print(f"  Found {len(models)} model files")
    print(f"  Found {len(migrations)} migration files")
    print(f"  Database schema: {'Available' if 'CREATE TABLE' in db_schema else 'Not available'}")

    # Build context
    context = "## SQLAlchemy Models\n\n"
    for filename, content in models.items():
        context += f"### {filename}\n```python\n{content}\n```\n\n"

    context += "## Recent Alembic Migrations\n\n"
    for migration in migrations[-5:]:  # Last 5 migrations
        context += f"### {migration['filename']}\n```python\n{migration['content']}\n```\n\n"

    context += f"## Database Schema\n```sql\n{db_schema[:10000]}\n```\n"

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
Analyze the following SQLAlchemy models and database schema for ABVTrends.

{context}

Please:
1. Compare models against database schema
2. Identify any mismatches
3. Generate Alembic migration code if needed
4. Suggest model fixes if needed
5. Provide recommendations for schema health

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


def save_results(audit_result: dict):
    """Save audit results."""

    RESULTS_DIR.mkdir(exist_ok=True)
    SUGGESTIONS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save JSON result
    json_file = RESULTS_DIR / f"model_audit_{timestamp}.json"
    with open(json_file, "w") as f:
        json.dump(audit_result, f, indent=2)

    # Save markdown report
    report_file = RESULTS_DIR / "model_audit.md"
    with open(report_file, "w") as f:
        f.write(f"# SQLAlchemy Model Audit Report\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")

        if "summary" in audit_result:
            f.write("## Summary\n")
            f.write(audit_result["summary"])
            f.write("\n\n")

        if "mismatches" in audit_result:
            f.write("## Schema Mismatches\n\n")
            for mismatch in audit_result["mismatches"]:
                severity = mismatch.get("severity", "unknown")
                f.write(f"### [{severity.upper()}] {mismatch.get('type', 'Unknown')}\n")
                f.write(f"- **Table:** `{mismatch.get('table', 'N/A')}`\n")
                f.write(f"- **Column:** `{mismatch.get('column', 'N/A')}`\n")
                f.write(f"- **Model:** {mismatch.get('model_definition', 'N/A')}\n")
                f.write(f"- **Database:** {mismatch.get('database_definition', 'N/A')}\n")
                f.write(f"- **Fix:** {mismatch.get('fix', 'N/A')}\n\n")

        if "migration_code" in audit_result and audit_result["migration_code"]:
            f.write("## Generated Migration\n")
            f.write("```python\n")
            f.write(audit_result["migration_code"])
            f.write("\n```\n\n")

            # Also save migration as separate file
            migration_file = SUGGESTIONS_DIR / f"migration_{timestamp}.py"
            with open(migration_file, "w") as mf:
                mf.write(audit_result["migration_code"])
            print(f"Migration saved to: {migration_file}")

        if "model_fixes" in audit_result:
            f.write("## Model Fixes\n\n")
            for fix in audit_result["model_fixes"]:
                f.write(f"### {fix.get('file', 'Unknown file')}\n")
                f.write(f"```python\n{fix.get('changes', '')}\n```\n\n")

        if "recommendations" in audit_result:
            f.write("## Recommendations\n\n")
            for rec in audit_result["recommendations"]:
                f.write(f"- {rec}\n")

        if "raw_response" in audit_result:
            f.write("## Raw Analysis\n\n")
            f.write(audit_result["raw_response"])

    print(f"\nAudit report saved to: {report_file}")


def main():
    """Main execution flow."""

    print("=" * 60)
    print("CLAUDE-MODEL-AUDITOR: SQLAlchemy Model Auditor")
    print("=" * 60)

    # Run audit
    audit_result = run_model_audit()

    if "error" in audit_result:
        print(f"\nError: {audit_result['error']}")
        return 1

    # Save results
    save_results(audit_result)

    # Print summary
    print("\n" + "=" * 60)
    print("AUDIT SUMMARY")
    print("=" * 60)

    if "summary" in audit_result:
        print(audit_result["summary"])

    if "mismatches" in audit_result:
        mismatches = audit_result["mismatches"]
        critical = len([m for m in mismatches if m.get("severity") == "critical"])
        high = len([m for m in mismatches if m.get("severity") == "high"])
        medium = len([m for m in mismatches if m.get("severity") == "medium"])

        print(f"\nMismatches found: {len(mismatches)}")
        print(f"  Critical: {critical}")
        print(f"  High: {high}")
        print(f"  Medium: {medium}")

    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
