#!/usr/bin/env python3
"""
CLAUDE-AUTO-DEPLOY: AI Deployment Gatekeeper

Analyzes:
- Test suite results
- Error logs
- Security findings
- Performance metrics
- API latency
- Model performance

Decides whether deployment is safe or should be blocked.
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
You are CLAUDE-AUTO-DEPLOY, the production deployment gatekeeper.

You analyze all available reports and decide whether a deployment is safe.

You evaluate:
1. **Test Results**
   - Unit test pass rate
   - Integration test results
   - E2E test status
   - Test coverage changes

2. **Security Analysis**
   - New vulnerabilities
   - Security scan findings
   - Dependency audit results
   - Authentication/authorization issues

3. **Performance Metrics**
   - Response time regressions
   - Memory usage changes
   - Database query performance
   - API latency impact

4. **Code Quality**
   - Bug predictions
   - Code complexity changes
   - Technical debt impact
   - Breaking changes

5. **Infrastructure Impact**
   - Database migrations
   - Config changes
   - Service dependencies
   - Rollback complexity

Decision Framework:
- ALLOW: All checks pass, no critical issues
- BLOCK: Any critical security vulnerability
- BLOCK: Test pass rate < 95%
- BLOCK: Performance regression > 20%
- BLOCK: Breaking API changes without version bump
- CAUTION: Minor issues that need monitoring

Output Format (JSON):
{
  "decision": "ALLOW|BLOCK|CAUTION",
  "confidence": 0-100,
  "summary": "Brief decision explanation",
  "checks": {
    "tests": {"status": "pass|fail|warn", "details": "..."},
    "security": {"status": "pass|fail|warn", "details": "..."},
    "performance": {"status": "pass|fail|warn", "details": "..."},
    "quality": {"status": "pass|fail|warn", "details": "..."},
    "infrastructure": {"status": "pass|fail|warn", "details": "..."}
  },
  "risks": [
    {
      "severity": "critical|high|medium|low",
      "area": "...",
      "description": "...",
      "mitigation": "..."
    }
  ],
  "required_fixes": ["..."],
  "recommendations": ["..."],
  "rollback_plan": "...",
  "monitoring_alerts": ["..."]
}
"""


def read_report(filename: str) -> str:
    """Read a report file if it exists."""

    # Try multiple locations
    paths = [
        RESULTS_DIR / filename,
        ROOT_DIR / "results" / filename,
        PROJECT_ROOT / filename
    ]

    for path in paths:
        if path.exists():
            try:
                return path.read_text()
            except:
                pass

    return f"[Report not found: {filename}]"


def gather_reports() -> dict:
    """Gather all available reports for analysis."""

    reports = {}

    # Test results
    reports["tests"] = read_report("qa_claude_output.md")
    if "[Report not found" in reports["tests"]:
        reports["tests"] = read_report("test_results.json")

    # Security report
    reports["security"] = read_report("security_report.md")
    if "[Report not found" in reports["security"]:
        reports["security"] = read_report("security_analysis.md")

    # Performance report
    reports["performance"] = read_report("performance_report.md")
    if "[Report not found" in reports["performance"]:
        reports["performance"] = read_report("performance_analysis.md")

    # Bug predictions
    reports["bugs"] = read_report("predictive_bug_report.md")

    # Dependency audit
    reports["dependencies"] = read_report("dependency_report.md")

    # Data quality
    reports["data_quality"] = read_report("data_quality_report.md")

    # Model audit
    reports["models"] = read_report("model_audit_report.md")

    return reports


def get_git_changes() -> str:
    """Get recent git changes for context."""

    import subprocess

    try:
        # Recent commits
        result = subprocess.run(
            ["git", "log", "--oneline", "-10"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT
        )
        commits = result.stdout

        # Changed files
        result = subprocess.run(
            ["git", "diff", "--stat", "HEAD~5"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT
        )
        changes = result.stdout

        return f"Recent Commits:\n{commits}\n\nChanges:\n{changes}"

    except:
        return "[Git info unavailable]"


def make_deploy_decision(reports: dict, git_changes: str) -> dict:
    """Make deployment decision with Claude."""

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {"error": "ANTHROPIC_API_KEY not set"}

    print("Analyzing deployment readiness...")

    # Build analysis input
    analysis_input = f"""
## Git Changes
{git_changes[:2000]}

## Test Results
{reports.get('tests', 'N/A')[:3000]}

## Security Report
{reports.get('security', 'N/A')[:3000]}

## Performance Report
{reports.get('performance', 'N/A')[:2000]}

## Bug Predictions
{reports.get('bugs', 'N/A')[:2000]}

## Dependency Audit
{reports.get('dependencies', 'N/A')[:2000]}

## Data Quality
{reports.get('data_quality', 'N/A')[:1500]}

## Model Audit
{reports.get('models', 'N/A')[:1500]}
"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=6000,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"""
Analyze the following reports and decide whether this deployment should proceed.

{analysis_input}

Make a deployment decision based on:
1. Test results (pass rate, coverage)
2. Security findings (vulnerabilities, risks)
3. Performance impact (regressions, latency)
4. Code quality (bugs, complexity)
5. Infrastructure changes (migrations, configs)

Return your decision as JSON.
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


def save_decision(decision: dict):
    """Save deployment decision."""

    RESULTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save JSON
    json_file = RESULTS_DIR / f"deploy_decision_{timestamp}.json"
    with open(json_file, "w") as f:
        json.dump(decision, f, indent=2)

    # Save markdown report
    report_file = RESULTS_DIR / "deploy_decision.md"
    with open(report_file, "w") as f:
        f.write("# Deployment Decision Report\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")

        if "decision" in decision:
            emoji = {
                "ALLOW": "✅",
                "BLOCK": "❌",
                "CAUTION": "⚠️"
            }.get(decision["decision"], "❓")

            f.write(f"## Decision: {emoji} {decision['decision']}\n\n")
            f.write(f"**Confidence:** {decision.get('confidence', 'N/A')}%\n\n")
            f.write(f"**Summary:** {decision.get('summary', 'N/A')}\n\n")

        if "checks" in decision:
            f.write("## Checks\n\n")
            f.write("| Area | Status | Details |\n")
            f.write("|------|--------|----------|\n")
            for area, check in decision["checks"].items():
                status_emoji = {
                    "pass": "✅",
                    "fail": "❌",
                    "warn": "⚠️"
                }.get(check.get("status"), "❓")
                f.write(f"| {area.title()} | {status_emoji} {check.get('status', 'N/A')} | {check.get('details', 'N/A')[:50]}... |\n")
            f.write("\n")

        if "risks" in decision and decision["risks"]:
            f.write("## Risks\n\n")
            for risk in decision["risks"]:
                severity = risk.get("severity", "unknown")
                emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(severity, "")
                f.write(f"### {emoji} [{severity.upper()}] {risk.get('area', 'General')}\n")
                f.write(f"{risk.get('description', 'N/A')}\n\n")
                f.write(f"**Mitigation:** {risk.get('mitigation', 'N/A')}\n\n")

        if "required_fixes" in decision and decision["required_fixes"]:
            f.write("## Required Fixes (Before Deploy)\n\n")
            for fix in decision["required_fixes"]:
                f.write(f"- {fix}\n")
            f.write("\n")

        if "recommendations" in decision:
            f.write("## Recommendations\n\n")
            for rec in decision.get("recommendations", []):
                f.write(f"- {rec}\n")
            f.write("\n")

        if "rollback_plan" in decision:
            f.write("## Rollback Plan\n\n")
            f.write(f"{decision['rollback_plan']}\n\n")

        if "monitoring_alerts" in decision:
            f.write("## Monitoring Alerts to Watch\n\n")
            for alert in decision.get("monitoring_alerts", []):
                f.write(f"- {alert}\n")

        if "raw_response" in decision:
            f.write("## Raw Analysis\n\n")
            f.write(decision["raw_response"])

    print(f"Decision saved to: {report_file}")
    return report_file


def main():
    """Main execution flow."""

    print("=" * 60)
    print("CLAUDE-AUTO-DEPLOY: AI Deployment Gatekeeper")
    print("=" * 60)

    RESULTS_DIR.mkdir(exist_ok=True)

    # Gather all reports
    print("\nGathering reports...")
    reports = gather_reports()

    available = [k for k, v in reports.items() if "[Report not found" not in v]
    print(f"  Available reports: {', '.join(available) if available else 'None'}")

    # Get git changes
    print("Getting git changes...")
    git_changes = get_git_changes()

    # Make decision
    decision = make_deploy_decision(reports, git_changes)

    if "error" in decision:
        print(f"\nError: {decision['error']}")
        return 1

    # Save decision
    report_file = save_decision(decision)

    # Print summary
    print("\n" + "=" * 60)
    print("DEPLOYMENT DECISION")
    print("=" * 60)

    if "decision" in decision:
        emoji = {"ALLOW": "✅", "BLOCK": "❌", "CAUTION": "⚠️"}.get(decision["decision"], "❓")
        print(f"\n{emoji} Decision: {decision['decision']}")
        print(f"Confidence: {decision.get('confidence', 'N/A')}%")
        print(f"\nSummary: {decision.get('summary', 'N/A')}")

        if decision.get("required_fixes"):
            print(f"\nRequired Fixes: {len(decision['required_fixes'])}")

        if decision.get("risks"):
            critical = len([r for r in decision["risks"] if r.get("severity") == "critical"])
            high = len([r for r in decision["risks"] if r.get("severity") == "high"])
            print(f"Risks: {len(decision['risks'])} ({critical} critical, {high} high)")

    print(f"\nFull report: {report_file}")

    # Return exit code based on decision
    if decision.get("decision") == "BLOCK":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
