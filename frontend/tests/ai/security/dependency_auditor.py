#!/usr/bin/env python3
"""
CLAUDE-DEPENDENCY-AUDITOR: AI Dependency Auditor

Checks for:
- Outdated packages
- Security vulnerabilities
- Deprecated APIs
- Suggested upgrades
- Breaking change warnings
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
You are CLAUDE-DEPENDENCY-AUDITOR, an expert in software dependency management and security.

You analyze:
1. Python packages (pip, requirements.txt)
2. Node.js packages (npm, package.json)
3. Security vulnerabilities
4. Outdated dependencies
5. Deprecated APIs
6. License compatibility

Your responsibilities:
1. Identify outdated packages and recommend updates
2. Flag security vulnerabilities with CVE references
3. Warn about breaking changes in major version updates
4. Suggest migration paths for deprecated packages
5. Check license compatibility
6. Prioritize updates by risk/impact

Output Format (JSON):
{
  "summary": {
    "python_packages": 0,
    "node_packages": 0,
    "outdated_critical": 0,
    "security_issues": 0,
    "health_score": 0-100
  },
  "python": {
    "outdated": [
      {
        "package": "name",
        "current": "version",
        "latest": "version",
        "severity": "critical|high|medium|low",
        "reason": "Why to update",
        "breaking_changes": ["..."],
        "migration_notes": "..."
      }
    ],
    "security": [
      {
        "package": "name",
        "vulnerability": "CVE-XXXX-XXXX",
        "severity": "critical|high|medium|low",
        "description": "...",
        "fix": "..."
      }
    ]
  },
  "node": {
    "outdated": [...],
    "security": [...]
  },
  "recommendations": [
    {
      "priority": "high|medium|low",
      "action": "...",
      "packages": ["..."],
      "reason": "..."
    }
  ]
}
"""


def get_python_outdated() -> str:
    """Get outdated Python packages."""

    try:
        result = subprocess.run(
            ["pip", "list", "--outdated", "--format=json"],
            capture_output=True,
            text=True,
            timeout=60
        )
        return result.stdout
    except Exception as e:
        return json.dumps({"error": str(e)})


def get_python_installed() -> str:
    """Get all installed Python packages."""

    try:
        result = subprocess.run(
            ["pip", "list", "--format=json"],
            capture_output=True,
            text=True,
            timeout=60
        )
        return result.stdout
    except Exception as e:
        return json.dumps({"error": str(e)})


def read_requirements() -> dict:
    """Read requirements.txt files."""

    requirements = {}

    req_files = [
        BACKEND_DIR / "requirements.txt",
        PROJECT_ROOT / "requirements.txt",
    ]

    for req_file in req_files:
        if req_file.exists():
            try:
                content = req_file.read_text()
                requirements[str(req_file.name)] = content
            except:
                pass

    return requirements


def read_package_json() -> dict:
    """Read package.json files."""

    packages = {}

    pkg_files = [
        FRONTEND_DIR / "package.json",
        PROJECT_ROOT / "package.json",
    ]

    for pkg_file in pkg_files:
        if pkg_file.exists():
            try:
                content = json.load(open(pkg_file))
                packages[str(pkg_file.relative_to(PROJECT_ROOT))] = {
                    "dependencies": content.get("dependencies", {}),
                    "devDependencies": content.get("devDependencies", {})
                }
            except:
                pass

    return packages


def get_npm_outdated() -> str:
    """Get outdated npm packages."""

    try:
        result = subprocess.run(
            ["npm", "outdated", "--json"],
            capture_output=True,
            text=True,
            cwd=FRONTEND_DIR,
            timeout=120
        )
        return result.stdout if result.stdout else "{}"
    except Exception as e:
        return json.dumps({"error": str(e)})


def get_npm_audit() -> str:
    """Get npm security audit."""

    try:
        result = subprocess.run(
            ["npm", "audit", "--json"],
            capture_output=True,
            text=True,
            cwd=FRONTEND_DIR,
            timeout=120
        )
        return result.stdout if result.stdout else "{}"
    except Exception as e:
        return json.dumps({"error": str(e)})


def run_pip_audit() -> str:
    """Run pip-audit for security vulnerabilities."""

    try:
        result = subprocess.run(
            ["pip-audit", "--format=json"],
            capture_output=True,
            text=True,
            timeout=120
        )
        return result.stdout if result.stdout else "[]"
    except FileNotFoundError:
        return json.dumps({"note": "pip-audit not installed. Install with: pip install pip-audit"})
    except Exception as e:
        return json.dumps({"error": str(e)})


def analyze_dependencies(
    python_outdated: str,
    python_installed: str,
    requirements: dict,
    npm_packages: dict,
    npm_outdated: str,
    npm_audit: str,
    pip_audit: str
) -> dict:
    """Analyze all dependency data with Claude."""

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {"error": "ANTHROPIC_API_KEY not set"}

    print("Analyzing dependencies with Claude...")

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"""
Analyze the dependencies for ABVTrends project.

## Python - Outdated Packages
{python_outdated}

## Python - All Installed
{python_installed[:5000]}

## Python - requirements.txt
{json.dumps(requirements, indent=2)}

## Python - Security Audit (pip-audit)
{pip_audit}

## Node.js - package.json
{json.dumps(npm_packages, indent=2)}

## Node.js - Outdated Packages
{npm_outdated}

## Node.js - Security Audit
{npm_audit[:5000]}

Please analyze and provide:
1. Summary of dependency health
2. Critical updates needed
3. Security vulnerabilities
4. Recommended upgrade path
5. Breaking change warnings

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


def save_report(analysis: dict):
    """Save dependency audit report."""

    RESULTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save JSON
    json_file = RESULTS_DIR / f"dependency_audit_{timestamp}.json"
    with open(json_file, "w") as f:
        json.dump(analysis, f, indent=2, default=str)

    # Save markdown report
    report_file = RESULTS_DIR / "dependency_report.md"
    with open(report_file, "w") as f:
        f.write("# Dependency Audit Report\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")

        if "summary" in analysis:
            summary = analysis["summary"]
            f.write("## Summary\n\n")
            f.write(f"- **Python Packages:** {summary.get('python_packages', 'N/A')}\n")
            f.write(f"- **Node Packages:** {summary.get('node_packages', 'N/A')}\n")
            f.write(f"- **Critical Outdated:** {summary.get('outdated_critical', 'N/A')}\n")
            f.write(f"- **Security Issues:** {summary.get('security_issues', 'N/A')}\n")
            f.write(f"- **Health Score:** {summary.get('health_score', 'N/A')}/100\n\n")

        if "python" in analysis:
            py = analysis["python"]

            if py.get("outdated"):
                f.write("## Python - Outdated Packages\n\n")
                f.write("| Package | Current | Latest | Severity |\n")
                f.write("|---------|---------|--------|----------|\n")
                for pkg in py["outdated"]:
                    f.write(f"| {pkg.get('package', 'N/A')} | {pkg.get('current', 'N/A')} | {pkg.get('latest', 'N/A')} | {pkg.get('severity', 'N/A')} |\n")
                f.write("\n")

            if py.get("security"):
                f.write("## Python - Security Vulnerabilities\n\n")
                for vuln in py["security"]:
                    f.write(f"### {vuln.get('package', 'Unknown')} - {vuln.get('vulnerability', 'N/A')}\n")
                    f.write(f"**Severity:** {vuln.get('severity', 'N/A')}\n\n")
                    f.write(f"{vuln.get('description', 'N/A')}\n\n")
                    f.write(f"**Fix:** {vuln.get('fix', 'N/A')}\n\n")

        if "node" in analysis:
            node = analysis["node"]

            if node.get("outdated"):
                f.write("## Node.js - Outdated Packages\n\n")
                f.write("| Package | Current | Latest | Severity |\n")
                f.write("|---------|---------|--------|----------|\n")
                for pkg in node["outdated"]:
                    f.write(f"| {pkg.get('package', 'N/A')} | {pkg.get('current', 'N/A')} | {pkg.get('latest', 'N/A')} | {pkg.get('severity', 'N/A')} |\n")
                f.write("\n")

            if node.get("security"):
                f.write("## Node.js - Security Vulnerabilities\n\n")
                for vuln in node["security"]:
                    f.write(f"### {vuln.get('package', 'Unknown')}\n")
                    f.write(f"**Severity:** {vuln.get('severity', 'N/A')}\n\n")
                    f.write(f"{vuln.get('description', 'N/A')}\n\n")

        if "recommendations" in analysis:
            f.write("## Recommendations\n\n")
            for rec in analysis["recommendations"]:
                priority = rec.get("priority", "medium")
                f.write(f"### [{priority.upper()}] {rec.get('action', 'N/A')}\n")
                f.write(f"**Packages:** {', '.join(rec.get('packages', []))}\n\n")
                f.write(f"{rec.get('reason', 'N/A')}\n\n")

        if "raw_response" in analysis:
            f.write("## Raw Analysis\n\n")
            f.write(analysis["raw_response"])

    print(f"\nReport saved to: {report_file}")


def main():
    """Main execution flow."""

    print("=" * 60)
    print("CLAUDE-DEPENDENCY-AUDITOR: AI Dependency Auditor")
    print("=" * 60)

    # Gather data
    print("\nGathering dependency information...")

    print("  Checking Python outdated packages...")
    python_outdated = get_python_outdated()

    print("  Getting Python installed packages...")
    python_installed = get_python_installed()

    print("  Reading requirements.txt...")
    requirements = read_requirements()

    print("  Running pip-audit...")
    pip_audit = run_pip_audit()

    print("  Reading package.json...")
    npm_packages = read_package_json()

    print("  Checking npm outdated packages...")
    npm_outdated = get_npm_outdated()

    print("  Running npm audit...")
    npm_audit = get_npm_audit()

    # Analyze
    analysis = analyze_dependencies(
        python_outdated,
        python_installed,
        requirements,
        npm_packages,
        npm_outdated,
        npm_audit,
        pip_audit
    )

    if "error" in analysis:
        print(f"\nError: {analysis['error']}")
        return 1

    # Save report
    save_report(analysis)

    # Print summary
    print("\n" + "=" * 60)
    print("DEPENDENCY AUDIT SUMMARY")
    print("=" * 60)

    if "summary" in analysis:
        summary = analysis["summary"]
        print(f"Health Score: {summary.get('health_score', 'N/A')}/100")
        print(f"Critical Updates: {summary.get('outdated_critical', 0)}")
        print(f"Security Issues: {summary.get('security_issues', 0)}")

    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
