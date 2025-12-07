#!/usr/bin/env python3
"""
CLAUDE-INCIDENT: AI Incident Response Coordinator

Analyzes production incidents and provides:
- Root cause analysis
- Impact assessment
- Mitigation steps
- Runbook generation
- Post-mortem templates
- Prevention recommendations
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
You are CLAUDE-INCIDENT, an expert Site Reliability Engineer (SRE) specializing in incident response and root cause analysis.

You analyze system incidents and provide actionable response guidance.

Analysis Areas:

1. **Incident Classification**
   - Severity levels (SEV1-SEV4)
   - Impact scope (users, services, data)
   - Category (performance, availability, security, data)
   - Time-sensitivity

2. **Root Cause Analysis**
   - Timeline reconstruction
   - Contributing factors
   - Direct vs indirect causes
   - System dependencies affected
   - 5 Whys analysis

3. **Impact Assessment**
   - User impact (affected users, user experience)
   - Business impact (revenue, reputation)
   - Data impact (integrity, loss, exposure)
   - Service degradation level

4. **Mitigation Steps**
   - Immediate actions
   - Short-term fixes
   - Long-term remediation
   - Rollback procedures
   - Communication templates

5. **Runbook Generation**
   - Step-by-step procedures
   - Escalation paths
   - On-call responsibilities
   - Tool commands
   - Verification steps

6. **Post-Mortem**
   - Blameless analysis
   - Lessons learned
   - Action items
   - Timeline documentation
   - Prevention measures

7. **Prevention Recommendations**
   - Monitoring improvements
   - Alerting thresholds
   - Code changes
   - Architecture improvements
   - Process changes

ABVTrends Context:
- FastAPI backend with async SQLAlchemy
- PostgreSQL database
- Next.js frontend
- ML forecasting components
- Web scraping workloads
- Critical features: Trend API, Product discovery, Scraper orchestration

Output Format (JSON):
{
  "incident_summary": {
    "title": "...",
    "severity": "SEV1|SEV2|SEV3|SEV4",
    "status": "investigating|identified|mitigated|resolved",
    "detected_at": "...",
    "resolved_at": "...",
    "duration": "...",
    "affected_services": ["..."],
    "affected_users": "X% of users"
  },
  "classification": {
    "category": "performance|availability|security|data",
    "subcategory": "...",
    "is_customer_facing": true,
    "is_data_related": false,
    "requires_security_review": false
  },
  "timeline": [
    {"time": "...", "event": "...", "source": "..."}
  ],
  "root_cause_analysis": {
    "direct_cause": "...",
    "contributing_factors": ["..."],
    "five_whys": [
      {"why": 1, "question": "Why did X happen?", "answer": "..."}
    ],
    "trigger": "...",
    "systemic_issues": ["..."]
  },
  "impact_assessment": {
    "user_impact": {
      "affected_users": "...",
      "user_experience": "...",
      "error_messages_shown": ["..."]
    },
    "business_impact": {
      "estimated_revenue_loss": "...",
      "reputation_impact": "...",
      "sla_violation": true
    },
    "technical_impact": {
      "services_degraded": ["..."],
      "data_integrity": "...",
      "cascading_failures": ["..."]
    }
  },
  "mitigation": {
    "immediate_actions": [
      {"action": "...", "command": "...", "owner": "...", "status": "done|in_progress|pending"}
    ],
    "short_term_fixes": ["..."],
    "rollback_procedure": "...",
    "verification_steps": ["..."]
  },
  "runbook": {
    "title": "...",
    "trigger_conditions": ["..."],
    "steps": [
      {"step": 1, "action": "...", "command": "...", "expected_result": "..."}
    ],
    "escalation": {
      "conditions": ["..."],
      "contacts": ["..."]
    },
    "rollback": "..."
  },
  "post_mortem": {
    "summary": "...",
    "what_went_well": ["..."],
    "what_went_wrong": ["..."],
    "where_we_got_lucky": ["..."],
    "action_items": [
      {"item": "...", "owner": "...", "priority": "P0|P1|P2", "due_date": "..."}
    ],
    "lessons_learned": ["..."]
  },
  "prevention": {
    "monitoring_improvements": ["..."],
    "alerting_changes": [
      {"metric": "...", "threshold": "...", "action": "..."}
    ],
    "code_changes": ["..."],
    "architecture_improvements": ["..."],
    "process_changes": ["..."]
  },
  "communication": {
    "internal_update": "...",
    "customer_update": "...",
    "status_page_update": "..."
  }
}
"""


def read_error_logs() -> str:
    """Read recent error logs if available."""

    log_sources = [
        RESULTS_DIR / "error_logs.txt",
        RESULTS_DIR / "qa_claude_output.md",
        PROJECT_ROOT / "logs" / "error.log",
        BACKEND_DIR / "logs" / "error.log"
    ]

    for log_file in log_sources:
        if log_file.exists():
            try:
                return log_file.read_text()[-10000:]  # Last 10K chars
            except:
                pass

    return "[No error logs found]"


def read_monitoring_data() -> dict:
    """Read any monitoring/performance data."""

    monitoring = {}

    # Check for performance reports
    perf_reports = [
        RESULTS_DIR / "performance_report.md",
        RESULTS_DIR / "performance_analysis.md"
    ]

    for report in perf_reports:
        if report.exists():
            try:
                monitoring["performance"] = report.read_text()[:5000]
            except:
                pass

    # Check for security reports
    sec_reports = [
        RESULTS_DIR / "security_report.md",
        RESULTS_DIR / "security_analysis.md"
    ]

    for report in sec_reports:
        if report.exists():
            try:
                monitoring["security"] = report.read_text()[:5000]
            except:
                pass

    # Check for test results
    test_reports = [
        RESULTS_DIR / "qa_claude_output.md",
        RESULTS_DIR / "test_results.json"
    ]

    for report in test_reports:
        if report.exists():
            try:
                monitoring["tests"] = report.read_text()[:5000]
            except:
                pass

    return monitoring


def read_system_architecture() -> str:
    """Read system architecture for context."""

    arch_files = [
        RESULTS_DIR / "code_map.md",
        PROJECT_ROOT / "DOCUMENTATION.md",
        PROJECT_ROOT / "docs" / "ARCHITECTURE.md"
    ]

    for arch_file in arch_files:
        if arch_file.exists():
            try:
                return arch_file.read_text()[:8000]
            except:
                pass

    return "[No architecture documentation found]"


def get_git_recent_changes() -> str:
    """Get recent git changes that might be relevant."""

    import subprocess

    try:
        # Recent commits
        result = subprocess.run(
            ["git", "log", "--oneline", "-20"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT
        )
        commits = result.stdout

        # Files changed recently
        result = subprocess.run(
            ["git", "diff", "--stat", "HEAD~10"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT
        )
        changes = result.stdout

        return f"Recent Commits:\n{commits}\n\nRecent Changes:\n{changes}"

    except:
        return "[Git info unavailable]"


def analyze_incident(
    incident_description: str,
    error_logs: str,
    monitoring: dict,
    architecture: str,
    git_changes: str
) -> dict:
    """Analyze incident with Claude."""

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {"error": "ANTHROPIC_API_KEY not set"}

    print("Analyzing incident...")

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=12000,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"""
Analyze this production incident and provide a comprehensive response.

## Incident Description
{incident_description}

## Error Logs
{error_logs[:5000]}

## Monitoring Data
### Performance
{monitoring.get('performance', 'N/A')[:3000]}

### Security
{monitoring.get('security', 'N/A')[:2000]}

### Test Results
{monitoring.get('tests', 'N/A')[:2000]}

## System Architecture
{architecture[:4000]}

## Recent Code Changes
{git_changes[:2000]}

## System Context
- FastAPI backend (Python 3.11, async)
- PostgreSQL database with SQLAlchemy 2.0
- Next.js frontend
- ML forecasting components
- Web scraping with rate limiting
- API endpoints for trends, products, discovery

Please provide:
1. Incident classification and severity
2. Timeline reconstruction
3. Root cause analysis (5 Whys)
4. Impact assessment
5. Immediate mitigation steps
6. Runbook for this type of incident
7. Post-mortem template
8. Prevention recommendations

Return as JSON.
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


def save_incident_report(analysis: dict, incident_id: str = None):
    """Save incident response report."""

    RESULTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if not incident_id:
        incident_id = f"INC-{timestamp[:8]}-001"

    # Save JSON
    json_file = RESULTS_DIR / f"incident_{incident_id}_{timestamp}.json"
    with open(json_file, "w") as f:
        json.dump(analysis, f, indent=2)

    # Save markdown report
    report_file = RESULTS_DIR / "incident_response.md"
    with open(report_file, "w") as f:
        f.write(f"# Incident Response Report: {incident_id}\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")

        if "incident_summary" in analysis:
            summary = analysis["incident_summary"]
            severity_emoji = {
                "SEV1": "🔴",
                "SEV2": "🟠",
                "SEV3": "🟡",
                "SEV4": "🟢"
            }.get(summary.get("severity", ""), "")

            f.write("## Incident Summary\n\n")
            f.write(f"**Title:** {summary.get('title', 'N/A')}\n\n")
            f.write(f"**Severity:** {severity_emoji} {summary.get('severity', 'N/A')}\n\n")
            f.write(f"**Status:** {summary.get('status', 'N/A')}\n\n")
            f.write(f"**Duration:** {summary.get('duration', 'N/A')}\n\n")
            f.write(f"**Affected Services:** {', '.join(summary.get('affected_services', []))}\n\n")
            f.write(f"**Affected Users:** {summary.get('affected_users', 'N/A')}\n\n")

        if "classification" in analysis:
            cls = analysis["classification"]
            f.write("## Classification\n\n")
            f.write(f"- **Category:** {cls.get('category', 'N/A')}\n")
            f.write(f"- **Subcategory:** {cls.get('subcategory', 'N/A')}\n")
            f.write(f"- **Customer Facing:** {'Yes' if cls.get('is_customer_facing') else 'No'}\n")
            f.write(f"- **Data Related:** {'Yes' if cls.get('is_data_related') else 'No'}\n")
            f.write(f"- **Security Review Required:** {'Yes' if cls.get('requires_security_review') else 'No'}\n\n")

        if "timeline" in analysis:
            f.write("## Timeline\n\n")
            f.write("| Time | Event | Source |\n")
            f.write("|------|-------|--------|\n")
            for event in analysis["timeline"]:
                f.write(f"| {event.get('time', 'N/A')} | {event.get('event', 'N/A')} | {event.get('source', 'N/A')} |\n")
            f.write("\n")

        if "root_cause_analysis" in analysis:
            rca = analysis["root_cause_analysis"]
            f.write("## Root Cause Analysis\n\n")
            f.write(f"**Direct Cause:** {rca.get('direct_cause', 'N/A')}\n\n")
            f.write(f"**Trigger:** {rca.get('trigger', 'N/A')}\n\n")

            if rca.get("contributing_factors"):
                f.write("**Contributing Factors:**\n")
                for factor in rca["contributing_factors"]:
                    f.write(f"- {factor}\n")
                f.write("\n")

            if rca.get("five_whys"):
                f.write("### 5 Whys Analysis\n\n")
                for why in rca["five_whys"]:
                    f.write(f"**Why {why.get('why', '?')}:** {why.get('question', 'N/A')}\n")
                    f.write(f"*Answer:* {why.get('answer', 'N/A')}\n\n")

            if rca.get("systemic_issues"):
                f.write("**Systemic Issues:**\n")
                for issue in rca["systemic_issues"]:
                    f.write(f"- {issue}\n")
                f.write("\n")

        if "impact_assessment" in analysis:
            impact = analysis["impact_assessment"]
            f.write("## Impact Assessment\n\n")

            if impact.get("user_impact"):
                user = impact["user_impact"]
                f.write("### User Impact\n")
                f.write(f"- Affected Users: {user.get('affected_users', 'N/A')}\n")
                f.write(f"- User Experience: {user.get('user_experience', 'N/A')}\n\n")

            if impact.get("business_impact"):
                biz = impact["business_impact"]
                f.write("### Business Impact\n")
                f.write(f"- Revenue Loss: {biz.get('estimated_revenue_loss', 'N/A')}\n")
                f.write(f"- Reputation: {biz.get('reputation_impact', 'N/A')}\n")
                f.write(f"- SLA Violation: {'Yes' if biz.get('sla_violation') else 'No'}\n\n")

        if "mitigation" in analysis:
            mit = analysis["mitigation"]
            f.write("## Mitigation\n\n")

            if mit.get("immediate_actions"):
                f.write("### Immediate Actions\n\n")
                f.write("| Action | Command | Owner | Status |\n")
                f.write("|--------|---------|-------|--------|\n")
                for action in mit["immediate_actions"]:
                    status_emoji = {"done": "✅", "in_progress": "🔄", "pending": "⏳"}.get(action.get("status", ""), "")
                    f.write(f"| {action.get('action', 'N/A')} | `{action.get('command', 'N/A')}` | {action.get('owner', 'N/A')} | {status_emoji} |\n")
                f.write("\n")

            if mit.get("rollback_procedure"):
                f.write("### Rollback Procedure\n")
                f.write(f"```\n{mit['rollback_procedure']}\n```\n\n")

            if mit.get("verification_steps"):
                f.write("### Verification Steps\n")
                for step in mit["verification_steps"]:
                    f.write(f"1. {step}\n")
                f.write("\n")

        if "runbook" in analysis:
            rb = analysis["runbook"]
            f.write("## Runbook\n\n")
            f.write(f"**Title:** {rb.get('title', 'N/A')}\n\n")

            if rb.get("trigger_conditions"):
                f.write("**Trigger Conditions:**\n")
                for cond in rb["trigger_conditions"]:
                    f.write(f"- {cond}\n")
                f.write("\n")

            if rb.get("steps"):
                f.write("**Steps:**\n\n")
                for step in rb["steps"]:
                    f.write(f"{step.get('step', '?')}. **{step.get('action', 'N/A')}**\n")
                    if step.get("command"):
                        f.write(f"   ```\n   {step['command']}\n   ```\n")
                    f.write(f"   Expected: {step.get('expected_result', 'N/A')}\n\n")

            if rb.get("escalation"):
                esc = rb["escalation"]
                f.write("**Escalation:**\n")
                if esc.get("conditions"):
                    f.write("Escalate if:\n")
                    for cond in esc["conditions"]:
                        f.write(f"- {cond}\n")
                f.write("\n")

        if "post_mortem" in analysis:
            pm = analysis["post_mortem"]
            f.write("## Post-Mortem\n\n")
            f.write(f"**Summary:** {pm.get('summary', 'N/A')}\n\n")

            if pm.get("what_went_well"):
                f.write("### What Went Well\n")
                for item in pm["what_went_well"]:
                    f.write(f"- {item}\n")
                f.write("\n")

            if pm.get("what_went_wrong"):
                f.write("### What Went Wrong\n")
                for item in pm["what_went_wrong"]:
                    f.write(f"- {item}\n")
                f.write("\n")

            if pm.get("action_items"):
                f.write("### Action Items\n\n")
                f.write("| Item | Owner | Priority | Due |\n")
                f.write("|------|-------|----------|-----|\n")
                for item in pm["action_items"]:
                    f.write(f"| {item.get('item', 'N/A')} | {item.get('owner', 'N/A')} | {item.get('priority', 'N/A')} | {item.get('due_date', 'N/A')} |\n")
                f.write("\n")

            if pm.get("lessons_learned"):
                f.write("### Lessons Learned\n")
                for lesson in pm["lessons_learned"]:
                    f.write(f"- {lesson}\n")
                f.write("\n")

        if "prevention" in analysis:
            prev = analysis["prevention"]
            f.write("## Prevention Recommendations\n\n")

            if prev.get("monitoring_improvements"):
                f.write("### Monitoring Improvements\n")
                for imp in prev["monitoring_improvements"]:
                    f.write(f"- {imp}\n")
                f.write("\n")

            if prev.get("alerting_changes"):
                f.write("### Alerting Changes\n\n")
                f.write("| Metric | Threshold | Action |\n")
                f.write("|--------|-----------|--------|\n")
                for alert in prev["alerting_changes"]:
                    f.write(f"| {alert.get('metric', 'N/A')} | {alert.get('threshold', 'N/A')} | {alert.get('action', 'N/A')} |\n")
                f.write("\n")

            if prev.get("code_changes"):
                f.write("### Code Changes Required\n")
                for change in prev["code_changes"]:
                    f.write(f"- {change}\n")
                f.write("\n")

        if "communication" in analysis:
            comm = analysis["communication"]
            f.write("## Communication Templates\n\n")

            if comm.get("internal_update"):
                f.write("### Internal Update\n")
                f.write(f"```\n{comm['internal_update']}\n```\n\n")

            if comm.get("customer_update"):
                f.write("### Customer Update\n")
                f.write(f"```\n{comm['customer_update']}\n```\n\n")

        if "raw_response" in analysis:
            f.write("## Raw Analysis\n\n")
            f.write(analysis["raw_response"])

    print(f"Report saved to: {report_file}")
    return report_file


def main():
    """Main execution flow."""

    print("=" * 60)
    print("CLAUDE-INCIDENT: AI Incident Response Coordinator")
    print("=" * 60)

    RESULTS_DIR.mkdir(exist_ok=True)

    # Get incident description from args or prompt
    if len(sys.argv) > 1:
        incident_description = " ".join(sys.argv[1:])
    else:
        incident_description = """
        Production incident: API endpoints returning 500 errors.
        Users reporting slow page loads and timeouts.
        Database connection errors in logs.
        Started approximately 30 minutes ago.
        Scraper service seems to be running heavy workloads.
        """
        print("\nNo incident description provided. Using example incident.")

    print(f"\nIncident: {incident_description[:100]}...")

    # Gather context
    print("\nGathering incident context...")

    print("Reading error logs...")
    error_logs = read_error_logs()

    print("Reading monitoring data...")
    monitoring = read_monitoring_data()
    print(f"  Available: {', '.join(monitoring.keys()) if monitoring else 'None'}")

    print("Reading system architecture...")
    architecture = read_system_architecture()

    print("Getting recent code changes...")
    git_changes = get_git_recent_changes()

    # Analyze incident
    analysis = analyze_incident(
        incident_description,
        error_logs,
        monitoring,
        architecture,
        git_changes
    )

    if "error" in analysis:
        print(f"\nError: {analysis['error']}")
        return 1

    # Save report
    report_file = save_incident_report(analysis)

    # Print summary
    print("\n" + "=" * 60)
    print("INCIDENT ANALYSIS COMPLETE")
    print("=" * 60)

    if "incident_summary" in analysis:
        summary = analysis["incident_summary"]
        severity_emoji = {"SEV1": "🔴", "SEV2": "🟠", "SEV3": "🟡", "SEV4": "🟢"}.get(summary.get("severity", ""), "")
        print(f"\nSeverity: {severity_emoji} {summary.get('severity', 'N/A')}")
        print(f"Status: {summary.get('status', 'N/A')}")
        print(f"Affected Services: {', '.join(summary.get('affected_services', []))}")

    if "root_cause_analysis" in analysis:
        rca = analysis["root_cause_analysis"]
        print(f"\nDirect Cause: {rca.get('direct_cause', 'N/A')}")

    if "mitigation" in analysis:
        mit = analysis["mitigation"]
        actions = mit.get("immediate_actions", [])
        print(f"\nImmediate Actions: {len(actions)}")
        for action in actions[:3]:
            print(f"  - {action.get('action', 'N/A')}")

    if "post_mortem" in analysis:
        pm = analysis["post_mortem"]
        items = pm.get("action_items", [])
        print(f"\nAction Items: {len(items)}")
        for item in items[:3]:
            print(f"  - [{item.get('priority', 'P?')}] {item.get('item', 'N/A')}")

    print(f"\nFull report: {report_file}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
