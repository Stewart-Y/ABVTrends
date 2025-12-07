#!/usr/bin/env python3
"""
CLAUDE-CHAOS: AI Chaos Engineering Planner

Generates chaos experiments to test system resilience:
- Database failure scenarios
- API timeout simulations
- Network latency injection
- Service crash recovery
- Resource exhaustion tests
- Auto-healing verification
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
You are CLAUDE-CHAOS, an expert in chaos engineering and resilience testing.

You design chaos experiments to test system reliability.

Experiment Categories:

1. **Infrastructure Chaos**
   - Server/pod termination
   - Network partition
   - DNS failure
   - Load balancer issues
   - Disk I/O failure

2. **Database Chaos**
   - Connection pool exhaustion
   - Slow queries
   - Replication lag
   - Primary failover
   - Data corruption simulation

3. **Application Chaos**
   - Memory leaks
   - CPU spike
   - Thread exhaustion
   - Exception injection
   - Deadlock simulation

4. **Network Chaos**
   - Latency injection
   - Packet loss
   - Bandwidth throttling
   - Connection timeouts
   - DNS resolution delay

5. **Dependency Chaos**
   - External API failure
   - Rate limiting
   - Slow responses
   - Incorrect responses
   - SSL/TLS issues

6. **Security Chaos**
   - Token expiration
   - Certificate issues
   - Authentication failures
   - Rate limit bypass attempts

For each experiment, provide:
- Hypothesis
- Steady state definition
- Injection method
- Blast radius
- Monitoring signals
- Rollback procedure
- Expected outcome
- Success criteria

Output Format (JSON):
{
  "summary": {
    "total_experiments": 10,
    "categories": ["infrastructure", "database", "..."],
    "risk_level": "low|medium|high",
    "recommended_order": ["exp-001", "exp-002"]
  },
  "steady_state": {
    "metrics": [
      {"name": "api_latency_p99", "baseline": "200ms", "threshold": "500ms"},
      {"name": "error_rate", "baseline": "0.1%", "threshold": "1%"}
    ],
    "health_checks": ["..."]
  },
  "experiments": [
    {
      "id": "chaos-001",
      "name": "Database Connection Pool Exhaustion",
      "category": "database",
      "risk_level": "medium",
      "hypothesis": "System gracefully degrades when DB connections exhausted",
      "steady_state": "API responds < 200ms, error rate < 0.1%",
      "injection": {
        "method": "...",
        "tool": "toxiproxy|chaos-monkey|custom",
        "script": "Python or bash script to inject failure",
        "duration": "5 minutes",
        "blast_radius": "50% of connections"
      },
      "expected_outcome": "...",
      "monitoring": {
        "dashboards": ["..."],
        "alerts": ["..."],
        "logs_to_watch": ["..."]
      },
      "rollback": {
        "automatic": true,
        "procedure": "...",
        "time_to_recover": "< 2 minutes"
      },
      "success_criteria": ["..."],
      "learnings": ["What we want to verify"]
    }
  ],
  "tools_needed": ["toxiproxy", "chaos-monkey", "locust"],
  "schedule": {
    "frequency": "weekly",
    "game_day_plan": "..."
  },
  "runbook": "Step-by-step execution guide"
}
"""


def read_architecture() -> str:
    """Read system architecture documentation."""

    doc_files = [
        PROJECT_ROOT / "DOCUMENTATION.md",
        PROJECT_ROOT / "docs" / "ARCHITECTURE.md",
        PROJECT_ROOT / "README.md",
        RESULTS_DIR / "code_map.md"
    ]

    for doc_file in doc_files:
        if doc_file.exists():
            try:
                return doc_file.read_text()
            except:
                pass

    return "[No architecture documentation found]"


def read_infrastructure() -> dict:
    """Read infrastructure configuration."""

    infra = {}

    # Docker compose
    compose_files = list(PROJECT_ROOT.glob("**/docker-compose*.yml"))
    for f in compose_files[:2]:
        try:
            infra[f.name] = f.read_text()
        except:
            pass

    # Kubernetes manifests
    k8s_files = list(PROJECT_ROOT.glob("**/*.yaml"))
    for f in k8s_files[:5]:
        if "k8s" in str(f) or "kubernetes" in str(f):
            try:
                infra[f.name] = f.read_text()
            except:
                pass

    # Environment files (sanitized)
    env_example = PROJECT_ROOT / ".env.example"
    if env_example.exists():
        try:
            infra["env_example"] = env_example.read_text()
        except:
            pass

    return infra


def read_service_dependencies() -> list:
    """Identify service dependencies from code."""

    dependencies = []

    # Check requirements
    req_file = PROJECT_ROOT / "backend" / "requirements.txt"
    if req_file.exists():
        try:
            content = req_file.read_text()
            if "psycopg" in content or "sqlalchemy" in content:
                dependencies.append("PostgreSQL Database")
            if "redis" in content:
                dependencies.append("Redis Cache")
            if "celery" in content:
                dependencies.append("Celery Workers")
            if "boto" in content:
                dependencies.append("AWS Services")
            if "httpx" in content or "requests" in content:
                dependencies.append("External HTTP APIs")
        except:
            pass

    # Check for common patterns in code
    backend_dir = PROJECT_ROOT / "backend"
    if backend_dir.exists():
        for file in backend_dir.rglob("*.py"):
            if "__pycache__" in str(file):
                continue
            try:
                content = file.read_text()
                if "async with" in content and "session" in content.lower():
                    if "Async Database" not in dependencies:
                        dependencies.append("Async Database Sessions")
                if "aiohttp" in content or "httpx" in content:
                    if "Async HTTP Client" not in dependencies:
                        dependencies.append("Async HTTP Client")
            except:
                pass

    return dependencies


def plan_chaos_experiments(architecture: str, infra: dict, dependencies: list) -> dict:
    """Plan chaos experiments with Claude."""

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {"error": "ANTHROPIC_API_KEY not set"}

    print("Planning chaos experiments...")

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=12000,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"""
Design chaos engineering experiments for this system.

## Project: ABVTrends
An AI-powered alcohol trend forecasting platform.

## System Architecture
{architecture[:8000]}

## Infrastructure Configuration
{json.dumps(list(infra.keys()), indent=2)}

## Service Dependencies
{json.dumps(dependencies, indent=2)}

## Tech Stack
- FastAPI backend (async)
- PostgreSQL database
- Next.js frontend
- Redis (if configured)
- External APIs for data scraping

Please design:
1. 8-10 chaos experiments covering different failure modes
2. Steady state definitions
3. Injection methods and scripts
4. Monitoring requirements
5. Rollback procedures
6. Game day execution plan

Focus on:
- Database resilience
- API timeout handling
- External dependency failures
- Memory/CPU exhaustion
- Network issues

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


def save_chaos_plan(plan: dict):
    """Save chaos engineering plan."""

    RESULTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save JSON
    json_file = RESULTS_DIR / f"chaos_plan_{timestamp}.json"
    with open(json_file, "w") as f:
        json.dump(plan, f, indent=2)

    # Save markdown report
    report_file = RESULTS_DIR / "chaos_plan.md"
    with open(report_file, "w") as f:
        f.write("# Chaos Engineering Plan\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")

        if "summary" in plan:
            summary = plan["summary"]
            f.write("## Summary\n\n")
            f.write(f"- **Total Experiments:** {summary.get('total_experiments', 'N/A')}\n")
            f.write(f"- **Categories:** {', '.join(summary.get('categories', []))}\n")
            f.write(f"- **Risk Level:** {summary.get('risk_level', 'N/A')}\n\n")

        if "steady_state" in plan:
            f.write("## Steady State Definition\n\n")
            steady = plan["steady_state"]

            if steady.get("metrics"):
                f.write("### Metrics\n\n")
                f.write("| Metric | Baseline | Threshold |\n")
                f.write("|--------|----------|----------|\n")
                for metric in steady["metrics"]:
                    f.write(f"| {metric.get('name', 'N/A')} | {metric.get('baseline', 'N/A')} | {metric.get('threshold', 'N/A')} |\n")
                f.write("\n")

        if "experiments" in plan:
            f.write("## Chaos Experiments\n\n")

            for exp in plan["experiments"]:
                risk_emoji = {
                    "low": "🟢",
                    "medium": "🟡",
                    "high": "🔴"
                }.get(exp.get("risk_level"), "")

                f.write(f"### {exp.get('id', 'EXP')}: {exp.get('name', 'Unknown')}\n\n")
                f.write(f"**Category:** {exp.get('category', 'N/A')} | **Risk:** {risk_emoji} {exp.get('risk_level', 'N/A')}\n\n")

                f.write(f"**Hypothesis:** {exp.get('hypothesis', 'N/A')}\n\n")

                if exp.get("injection"):
                    injection = exp["injection"]
                    f.write("**Injection:**\n")
                    f.write(f"- Method: {injection.get('method', 'N/A')}\n")
                    f.write(f"- Tool: {injection.get('tool', 'N/A')}\n")
                    f.write(f"- Duration: {injection.get('duration', 'N/A')}\n")
                    f.write(f"- Blast Radius: {injection.get('blast_radius', 'N/A')}\n\n")

                    if injection.get("script"):
                        f.write("**Script:**\n```bash\n")
                        f.write(injection["script"])
                        f.write("\n```\n\n")

                f.write(f"**Expected Outcome:** {exp.get('expected_outcome', 'N/A')}\n\n")

                if exp.get("monitoring"):
                    monitoring = exp["monitoring"]
                    f.write("**Monitoring:**\n")
                    if monitoring.get("alerts"):
                        f.write(f"- Alerts: {', '.join(monitoring['alerts'])}\n")
                    if monitoring.get("logs_to_watch"):
                        f.write(f"- Logs: {', '.join(monitoring['logs_to_watch'])}\n")
                    f.write("\n")

                if exp.get("rollback"):
                    rollback = exp["rollback"]
                    f.write("**Rollback:**\n")
                    f.write(f"- Automatic: {'Yes' if rollback.get('automatic') else 'No'}\n")
                    f.write(f"- Recovery Time: {rollback.get('time_to_recover', 'N/A')}\n")
                    f.write(f"- Procedure: {rollback.get('procedure', 'N/A')}\n\n")

                if exp.get("success_criteria"):
                    f.write("**Success Criteria:**\n")
                    for criteria in exp["success_criteria"]:
                        f.write(f"- {criteria}\n")
                    f.write("\n")

                f.write("---\n\n")

        if "tools_needed" in plan:
            f.write("## Required Tools\n\n")
            for tool in plan["tools_needed"]:
                f.write(f"- {tool}\n")
            f.write("\n")

        if "runbook" in plan:
            f.write("## Runbook\n\n")
            f.write(plan["runbook"])
            f.write("\n")

        if "raw_response" in plan:
            f.write("## Raw Analysis\n\n")
            f.write(plan["raw_response"])

    print(f"Plan saved to: {report_file}")
    return report_file


def main():
    """Main execution flow."""

    print("=" * 60)
    print("CLAUDE-CHAOS: AI Chaos Engineering Planner")
    print("=" * 60)

    RESULTS_DIR.mkdir(exist_ok=True)

    # Read system information
    print("\nReading system architecture...")
    architecture = read_architecture()

    print("Reading infrastructure configuration...")
    infra = read_infrastructure()
    print(f"  Found {len(infra)} config files")

    print("Identifying service dependencies...")
    dependencies = read_service_dependencies()
    print(f"  Found {len(dependencies)} dependencies")

    # Plan experiments
    plan = plan_chaos_experiments(architecture, infra, dependencies)

    if "error" in plan:
        print(f"\nError: {plan['error']}")
        return 1

    # Save plan
    report_file = save_chaos_plan(plan)

    # Print summary
    print("\n" + "=" * 60)
    print("CHAOS PLANNING COMPLETE")
    print("=" * 60)

    if "summary" in plan:
        summary = plan["summary"]
        print(f"Total Experiments: {summary.get('total_experiments', 'N/A')}")
        print(f"Risk Level: {summary.get('risk_level', 'N/A')}")

    if "experiments" in plan:
        print(f"\nExperiments designed: {len(plan['experiments'])}")
        for exp in plan["experiments"][:5]:
            print(f"  - [{exp.get('risk_level', '?')}] {exp.get('name', 'Unknown')}")

    print(f"\nFull plan: {report_file}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
