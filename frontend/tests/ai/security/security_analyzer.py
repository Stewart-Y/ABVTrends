#!/usr/bin/env python3
"""
CLAUDE-SECURITY: AI Security Analyzer

Runs Bandit security scanner on backend code and uses Claude to analyze
findings, explain impact, and recommend mitigations.
"""

import os
import sys
import json
import subprocess
from datetime import datetime
from pathlib import Path

# Load .env file if it exists
SCRIPT_DIR = Path(__file__).parent
ROOT_DIR = SCRIPT_DIR.parent
BACKEND_DIR = ROOT_DIR.parent.parent.parent / "backend"
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

# Initialize Anthropic client
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """
You are CLAUDE-SECURITY, an AI security auditor specializing in Python web application security.

ABVTrends Tech Stack:
- Backend: FastAPI, Python 3.11, SQLAlchemy, PostgreSQL
- Authentication: JWT tokens
- External APIs: Anthropic Claude API, web scraping

You analyze Bandit security scan results and:
1. Explain each finding in plain English
2. Assess severity and real-world impact
3. Determine if it's a true positive or false positive
4. Provide specific code fixes
5. Recommend security best practices

Security Categories:
- Injection (SQL, Command, XSS)
- Authentication/Authorization
- Cryptography
- Data Exposure
- Configuration
- Dependencies

Severity Levels:
- CRITICAL: Immediate fix required, exploitable vulnerability
- HIGH: Fix soon, significant security risk
- MEDIUM: Should fix, moderate risk
- LOW: Consider fixing, minor risk
- INFO: Informational, best practice recommendation

Output Format:
1. Executive Summary
2. Findings by Severity
3. Detailed Analysis per Finding
4. Recommended Fixes with Code
5. Security Hardening Recommendations
"""


def run_bandit_scan() -> dict:
    """Run Bandit security scanner on backend code."""

    results_dir = ROOT_DIR / "results"
    results_dir.mkdir(exist_ok=True)
    raw_output = results_dir / "security_raw.json"

    print(f"Running Bandit security scan on {BACKEND_DIR}...")

    if not BACKEND_DIR.exists():
        print(f"Error: Backend directory not found at {BACKEND_DIR}")
        return {"error": "Backend directory not found"}

    try:
        # Run bandit with JSON output
        result = subprocess.run(
            [
                "bandit",
                "-r", str(BACKEND_DIR),
                "-f", "json",
                "-o", str(raw_output),
                "--exclude", "**/tests/**,**/venv/**,**/__pycache__/**",
                "-ll"  # Only medium and higher severity
            ],
            capture_output=True,
            text=True
        )

        # Bandit returns non-zero if it finds issues, which is expected
        if raw_output.exists():
            with open(raw_output) as f:
                return json.load(f)
        else:
            # Try to parse stderr for errors
            return {"error": result.stderr or "Bandit scan failed", "stdout": result.stdout}

    except FileNotFoundError:
        print("Error: Bandit not installed. Run: pip install bandit")
        return {"error": "Bandit not installed. Run: pip install bandit"}
    except Exception as e:
        return {"error": str(e)}


def scan_for_secrets() -> list:
    """Scan for potential hardcoded secrets."""

    secrets_patterns = [
        ("API Key", r'["\'](?:api[_-]?key|apikey)["\']?\s*[:=]\s*["\'][a-zA-Z0-9_-]{20,}["\']'),
        ("Password", r'["\'](?:password|passwd|pwd)["\']?\s*[:=]\s*["\'][^"\']+["\']'),
        ("Secret", r'["\'](?:secret|token)["\']?\s*[:=]\s*["\'][a-zA-Z0-9_-]{20,}["\']'),
        ("Connection String", r'(?:postgresql|mysql|mongodb)://[^\s]+'),
        ("JWT Secret", r'["\'](?:jwt[_-]?secret|secret[_-]?key)["\']?\s*[:=]\s*["\'][^"\']+["\']'),
    ]

    findings = []
    import re

    if BACKEND_DIR.exists():
        for file in BACKEND_DIR.rglob("*.py"):
            # Skip virtual environments and cache
            if "venv" in str(file) or "__pycache__" in str(file):
                continue

            try:
                content = file.read_text()
                for pattern_name, pattern in secrets_patterns:
                    matches = re.finditer(pattern, content, re.IGNORECASE)
                    for match in matches:
                        line_num = content[:match.start()].count('\n') + 1
                        findings.append({
                            "type": pattern_name,
                            "file": str(file.relative_to(BACKEND_DIR)),
                            "line": line_num,
                            "match": match.group()[:50] + "..." if len(match.group()) > 50 else match.group()
                        })
            except:
                continue

    return findings


def analyze_dependencies() -> dict:
    """Check for known vulnerable dependencies."""

    requirements_file = BACKEND_DIR / "requirements.txt"
    if not requirements_file.exists():
        return {"error": "requirements.txt not found"}

    deps = []
    try:
        content = requirements_file.read_text()
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                deps.append(line)
    except:
        pass

    return {"dependencies": deps}


def analyze_with_claude(bandit_results: dict, secrets: list, deps: dict) -> str:
    """Send security findings to Claude for analysis."""

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return "Error: ANTHROPIC_API_KEY not set"

    print("\nSending to Claude for security analysis...")

    # Summarize findings
    findings_summary = {
        "bandit_results": bandit_results,
        "potential_secrets": secrets,
        "dependencies": deps
    }

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8000,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"""
## Security Scan Results

### Bandit Static Analysis
{json.dumps(bandit_results, indent=2)}

### Potential Hardcoded Secrets
{json.dumps(secrets, indent=2)}

### Dependencies
{json.dumps(deps, indent=2)}

---

Please provide a comprehensive security analysis:
1. Executive summary of security posture
2. Critical and high severity findings with fixes
3. Code patches for each vulnerability
4. Security hardening recommendations
5. CI/CD security integration suggestions
"""
            }
        ]
    )

    return message.content[0].text


def save_report(report: str, bandit_results: dict):
    """Save the security report."""

    results_dir = ROOT_DIR / "results"
    results_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save detailed report
    report_file = results_dir / f"security_report_{timestamp}.md"
    with open(report_file, "w") as f:
        f.write(f"# ABVTrends Security Report\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")
        f.write("---\n\n")
        f.write(report)

    print(f"\nSecurity report saved to: {report_file}")

    # Save to standard location
    standard_report = results_dir / "security_report.md"
    with open(standard_report, "w") as f:
        f.write(f"# ABVTrends Security Report\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")
        f.write("---\n\n")
        f.write(report)

    # Generate summary for CI
    issues = bandit_results.get("results", [])
    high_severity = len([i for i in issues if i.get("issue_severity") == "HIGH"])
    medium_severity = len([i for i in issues if i.get("issue_severity") == "MEDIUM"])

    summary = {
        "timestamp": timestamp,
        "total_issues": len(issues),
        "high_severity": high_severity,
        "medium_severity": medium_severity,
        "passed": high_severity == 0
    }

    summary_file = results_dir / "security_summary.json"
    with open(summary_file, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"Security summary saved to: {summary_file}")

    return summary


def main():
    """Main execution flow."""

    print("=" * 60)
    print("CLAUDE-SECURITY: AI Security Analyzer")
    print("=" * 60)

    # Run Bandit scan
    bandit_results = run_bandit_scan()

    if "error" in bandit_results:
        print(f"Warning: {bandit_results['error']}")
        bandit_results = {"results": [], "error": bandit_results["error"]}

    issues = bandit_results.get("results", [])
    print(f"\nBandit found {len(issues)} issues")

    # Scan for secrets
    print("\nScanning for hardcoded secrets...")
    secrets = scan_for_secrets()
    print(f"Found {len(secrets)} potential secrets")

    # Check dependencies
    print("\nAnalyzing dependencies...")
    deps = analyze_dependencies()

    # Analyze with Claude
    report = analyze_with_claude(bandit_results, secrets, deps)

    if report.startswith("Error:"):
        print(report)
        return 1

    # Save report
    summary = save_report(report, bandit_results)

    # Print summary
    print("\n" + "=" * 60)
    print("SECURITY SCAN SUMMARY")
    print("=" * 60)
    print(f"Total issues: {summary['total_issues']}")
    print(f"High severity: {summary['high_severity']}")
    print(f"Medium severity: {summary['medium_severity']}")
    print(f"Status: {'PASSED' if summary['passed'] else 'FAILED'}")
    print("=" * 60)

    return 0 if summary['passed'] else 1


if __name__ == "__main__":
    sys.exit(main())
