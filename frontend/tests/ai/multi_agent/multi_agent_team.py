#!/usr/bin/env python3
"""
CLAUDE-TEAM: AI Multi-Agent Team Coordinator

Orchestrates a full development team of AI agents:
- PM: Product requirements and stories
- Architect: System design and codebase mapping
- Engineer: Feature implementation
- QA: Testing and quality assurance
- Release: Deployment and release notes
- Docs: Documentation generation
- Marketing: Growth and marketing content
"""

import os
import sys
import subprocess
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict

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


# Agent definitions
AGENTS = {
    "pm": {
        "name": "Product Manager",
        "emoji": "🧠",
        "script": "pm/prd_generator.py",
        "description": "Generates PRDs and user stories",
        "outputs": ["prd_*.md", "user_stories_*.json"]
    },
    "architect": {
        "name": "System Architect",
        "emoji": "🏗️",
        "script": "docs/map_generator.py",
        "description": "Creates architecture diagrams and codebase maps",
        "outputs": ["code_map*.md"]
    },
    "engineer": {
        "name": "Software Engineer",
        "emoji": "👨‍💻",
        "script": "feature/feature_builder.py",
        "description": "Generates production code from stories",
        "outputs": ["feature_build*.md"]
    },
    "qa": {
        "name": "QA Engineer",
        "emoji": "🧪",
        "script": "run_claude_tests.py",
        "description": "Runs tests and self-heals failures",
        "outputs": ["qa_claude_output.md"]
    },
    "security": {
        "name": "Security Analyst",
        "emoji": "🔒",
        "script": "security/security_analyzer.py",
        "description": "Analyzes security vulnerabilities",
        "outputs": ["security_report*.md"]
    },
    "bugs": {
        "name": "Bug Prophet",
        "emoji": "🔮",
        "script": "predictive/predictive_bug_finder.py",
        "description": "Predicts potential bugs",
        "outputs": ["predictive_bug_report.md"]
    },
    "release": {
        "name": "Release Manager",
        "emoji": "🚀",
        "script": "release/release_manager.py",
        "description": "Generates changelog and release notes",
        "outputs": ["release_*.md", "CHANGELOG.md"]
    },
    "docs": {
        "name": "Documentation Writer",
        "emoji": "📚",
        "script": "docs/doc_writer.py",
        "description": "Generates project documentation",
        "outputs": ["documentation_*.md"]
    },
    "wiki": {
        "name": "Wiki Updater",
        "emoji": "📖",
        "script": "wiki/wiki_updater.py",
        "description": "Updates GitHub wiki",
        "outputs": ["wiki_updates*.md"]
    },
    "ux": {
        "name": "UX Analyst",
        "emoji": "🎨",
        "script": "ux/ux_agent.py",
        "description": "Analyzes UI/UX",
        "outputs": ["ux_report.md"]
    },
    "deploy": {
        "name": "Deploy Gatekeeper",
        "emoji": "🚦",
        "script": "deploy/auto_deploy_decider.py",
        "description": "Decides if deployment is safe",
        "outputs": ["deploy_decision.md"]
    },
    "marketing": {
        "name": "Marketing Specialist",
        "emoji": "📈",
        "script": "marketing/marketing_agent.py",
        "description": "Creates marketing content",
        "outputs": ["marketing_output.md"]
    },
    "infra": {
        "name": "Infrastructure Engineer",
        "emoji": "☁️",
        "script": "ops/infra_optimizer.py",
        "description": "Optimizes infrastructure",
        "outputs": ["infra_optimization.md"]
    },
    "ml": {
        "name": "ML Engineer",
        "emoji": "🤖",
        "script": "ml/model_trainer.py",
        "description": "Manages ML model training",
        "outputs": ["model_retrain_plan.md"]
    }
}

# Team compositions
TEAMS = {
    "product": {
        "name": "Product Team",
        "agents": ["pm", "architect", "ux"],
        "description": "Product planning and design"
    },
    "engineering": {
        "name": "Engineering Team",
        "agents": ["architect", "engineer", "qa", "bugs"],
        "description": "Development and testing"
    },
    "release": {
        "name": "Release Team",
        "agents": ["qa", "security", "deploy", "release"],
        "description": "Release preparation"
    },
    "growth": {
        "name": "Growth Team",
        "agents": ["marketing", "docs", "wiki"],
        "description": "Marketing and documentation"
    },
    "platform": {
        "name": "Platform Team",
        "agents": ["infra", "security", "ml"],
        "description": "Infrastructure and ML"
    },
    "full": {
        "name": "Full Team",
        "agents": ["pm", "architect", "engineer", "qa", "security", "bugs", "docs", "release", "deploy"],
        "description": "Complete development cycle"
    }
}


class MultiAgentTeam:
    """Coordinates multiple AI agents as a team."""

    def __init__(self):
        self.results = {}
        self.log_file = None
        self.start_time = None

    def setup_logging(self):
        """Setup team execution logging."""
        RESULTS_DIR.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = RESULTS_DIR / f"team_execution_{timestamp}.md"

        with open(self.log_file, "w") as f:
            f.write("# AI Team Execution Log\n\n")
            f.write(f"Started: {datetime.now().isoformat()}\n\n")
            f.write("---\n\n")

    def log(self, message: str, level: str = "info"):
        """Log message to file and console."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = {
            "info": "ℹ️",
            "success": "✅",
            "error": "❌",
            "warning": "⚠️",
            "agent": "🤖"
        }.get(level, "")

        print(f"[{timestamp}] {prefix} {message}")

        if self.log_file:
            with open(self.log_file, "a") as f:
                f.write(f"**[{timestamp}]** {message}\n\n")

    def run_agent(self, agent_key: str, args: List[str] = None) -> Dict:
        """Run a single agent."""
        if agent_key not in AGENTS:
            return {"success": False, "error": f"Unknown agent: {agent_key}"}

        agent = AGENTS[agent_key]
        script_path = ROOT_DIR / agent["script"]

        if not script_path.exists():
            return {"success": False, "error": f"Script not found: {script_path}"}

        self.log(f"{agent['emoji']} {agent['name']} starting...", "agent")

        cmd = [sys.executable, str(script_path)]
        if args:
            cmd.extend(args)

        try:
            start = datetime.now()
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,
                cwd=ROOT_DIR
            )
            duration = (datetime.now() - start).total_seconds()

            success = result.returncode == 0

            if success:
                self.log(f"{agent['emoji']} {agent['name']} completed ({duration:.1f}s)", "success")
            else:
                self.log(f"{agent['emoji']} {agent['name']} failed ({duration:.1f}s)", "error")

            return {
                "success": success,
                "duration": duration,
                "returncode": result.returncode,
                "stdout": result.stdout[-2000:] if result.stdout else "",
                "stderr": result.stderr[-1000:] if result.stderr else ""
            }

        except subprocess.TimeoutExpired:
            self.log(f"{agent['emoji']} {agent['name']} timed out", "error")
            return {"success": False, "error": "Timeout"}

        except Exception as e:
            self.log(f"{agent['emoji']} {agent['name']} error: {e}", "error")
            return {"success": False, "error": str(e)}

    def run_team(self, team_key: str, stop_on_error: bool = False) -> Dict:
        """Run a predefined team."""
        if team_key not in TEAMS:
            return {"success": False, "error": f"Unknown team: {team_key}"}

        team = TEAMS[team_key]
        self.log(f"Assembling {team['name']}: {team['description']}")

        return self.run_agents(team["agents"], stop_on_error)

    def run_agents(self, agents: List[str], stop_on_error: bool = False) -> Dict:
        """Run a list of agents in sequence."""
        self.setup_logging()
        self.start_time = datetime.now()
        self.results = {}

        self.log(f"Team assembled: {len(agents)} agents")
        self.log(f"Agents: {' → '.join([AGENTS[a]['emoji'] + ' ' + AGENTS[a]['name'] for a in agents if a in AGENTS])}")

        success_count = 0
        error_count = 0
        total_duration = 0

        for agent_key in agents:
            if agent_key not in AGENTS:
                self.log(f"Skipping unknown agent: {agent_key}", "warning")
                continue

            result = self.run_agent(agent_key)
            self.results[agent_key] = result

            if result.get("success"):
                success_count += 1
            else:
                error_count += 1
                if stop_on_error:
                    self.log("Pipeline stopped due to error", "warning")
                    break

            total_duration += result.get("duration", 0)

        pipeline_duration = (datetime.now() - self.start_time).total_seconds()

        summary = {
            "success": error_count == 0,
            "agents_run": len(self.results),
            "success_count": success_count,
            "error_count": error_count,
            "pipeline_duration": pipeline_duration,
            "agent_duration": total_duration,
            "results": self.results
        }

        self.save_summary(summary)
        return summary

    def save_summary(self, summary: Dict):
        """Save team execution summary."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save JSON
        json_file = RESULTS_DIR / f"team_summary_{timestamp}.json"
        json_summary = {
            "timestamp": timestamp,
            "success": summary["success"],
            "agents_run": summary["agents_run"],
            "success_count": summary["success_count"],
            "error_count": summary["error_count"],
            "pipeline_duration": summary["pipeline_duration"],
            "agents": {
                k: {
                    "success": v.get("success"),
                    "duration": v.get("duration"),
                    "error": v.get("error")
                }
                for k, v in summary.get("results", {}).items()
            }
        }

        with open(json_file, "w") as f:
            json.dump(json_summary, f, indent=2)

        # Update log file
        if self.log_file:
            with open(self.log_file, "a") as f:
                f.write("\n---\n\n")
                f.write("## Team Execution Summary\n\n")
                f.write(f"- **Status:** {'✅ Success' if summary['success'] else '❌ Failed'}\n")
                f.write(f"- **Agents Run:** {summary['agents_run']}\n")
                f.write(f"- **Successful:** {summary['success_count']}\n")
                f.write(f"- **Failed:** {summary['error_count']}\n")
                f.write(f"- **Duration:** {summary['pipeline_duration']:.1f}s\n\n")

                f.write("### Agent Results\n\n")
                f.write("| Agent | Status | Duration |\n")
                f.write("|-------|--------|----------|\n")
                for key, result in summary.get("results", {}).items():
                    agent = AGENTS.get(key, {})
                    status = "✅" if result.get("success") else "❌"
                    duration = f"{result.get('duration', 0):.1f}s"
                    f.write(f"| {agent.get('emoji', '')} {agent.get('name', key)} | {status} | {duration} |\n")

        self.log(f"Summary saved to: {json_file}")


def print_help():
    """Print usage help."""
    print("""
CLAUDE-TEAM: AI Multi-Agent Team Coordinator

Usage:
  python multi_agent_team.py <team>         Run a predefined team
  python multi_agent_team.py <agent>        Run a single agent
  python multi_agent_team.py a1 a2 a3       Run specific agents in order
  python multi_agent_team.py --list         List available agents and teams

Teams:
""")
    for key, team in TEAMS.items():
        agents_str = " → ".join([AGENTS[a]["emoji"] for a in team["agents"] if a in AGENTS])
        print(f"  {key:12} {team['name']:20} {agents_str}")

    print("""
Agents:
""")
    for key, agent in AGENTS.items():
        print(f"  {key:12} {agent['emoji']} {agent['name']:20} {agent['description']}")

    print("""
Examples:
  python multi_agent_team.py full           Run full development team
  python multi_agent_team.py engineering    Run engineering team
  python multi_agent_team.py pm engineer qa Run PM then Engineer then QA
  python multi_agent_team.py qa             Run only QA agent
""")


def main():
    """Main execution flow."""
    args = sys.argv[1:]

    if not args or "--help" in args or "-h" in args:
        print_help()
        return 0

    if "--list" in args:
        print_help()
        return 0

    team = MultiAgentTeam()

    print("=" * 60)
    print("CLAUDE-TEAM: AI Multi-Agent Team Coordinator")
    print("=" * 60)

    # Check if it's a team
    if len(args) == 1 and args[0] in TEAMS:
        team_key = args[0]
        team_def = TEAMS[team_key]
        print(f"\nAssembling {team_def['name']}")
        print(f"Description: {team_def['description']}")
        print(f"Agents: {' → '.join([AGENTS[a]['emoji'] + ' ' + AGENTS[a]['name'] for a in team_def['agents'] if a in AGENTS])}\n")

        summary = team.run_team(team_key)

    # Check if it's a single agent
    elif len(args) == 1 and args[0] in AGENTS:
        agent_key = args[0]
        agent = AGENTS[agent_key]
        print(f"\nRunning {agent['emoji']} {agent['name']}\n")

        summary = team.run_agents([agent_key])

    # Multiple agents specified
    elif all(a in AGENTS for a in args):
        print(f"\nRunning custom team: {' → '.join([AGENTS[a]['emoji'] for a in args])}\n")
        summary = team.run_agents(args)

    else:
        unknown = [a for a in args if a not in AGENTS and a not in TEAMS]
        print(f"Unknown agents/teams: {unknown}")
        print_help()
        return 1

    # Print final summary
    print("\n" + "=" * 60)
    print("TEAM EXECUTION COMPLETE")
    print("=" * 60)
    print(f"Status: {'✅ Success' if summary['success'] else '❌ Failed'}")
    print(f"Agents: {summary['success_count']}/{summary['agents_run']} successful")
    print(f"Duration: {summary['pipeline_duration']:.1f}s")

    if team.log_file:
        print(f"\nLog: {team.log_file}")

    return 0 if summary["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
