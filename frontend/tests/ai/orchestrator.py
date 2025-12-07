#!/usr/bin/env python3
"""
CLAUDE-ORCHESTRATOR: AI Multi-Agent Pipeline

Orchestrates the full AI development pipeline:
PM → Engineering → QA → Docs → Release

Pipeline stages:
1. PRD Generation (PM)
2. Feature Building (Engineering)
3. Test Generation (QA)
4. Documentation (Docs)
5. Release Notes (Release)
"""

import os
import sys
import subprocess
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

# Setup paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent
RESULTS_DIR = SCRIPT_DIR / "results"

# Agent scripts
AGENTS = {
    "pm": {
        "name": "Product Manager",
        "script": "pm/prd_generator.py",
        "description": "Generates PRD and user stories"
    },
    "sprint": {
        "name": "Sprint Planner",
        "script": "pm/sprint_planner.py",
        "description": "Plans sprint from backlog"
    },
    "feature": {
        "name": "Feature Builder",
        "script": "feature/feature_builder.py",
        "description": "Generates production code from stories"
    },
    "qa": {
        "name": "QA Engineer",
        "script": "run_claude_tests.py",
        "description": "Runs tests and self-heals failures"
    },
    "ux": {
        "name": "UX Analyst",
        "script": "ux/ux_agent.py",
        "description": "Analyzes UI/UX and recommends improvements"
    },
    "docs": {
        "name": "Documentation Writer",
        "script": "docs/doc_writer.py",
        "description": "Generates project documentation"
    },
    "wiki": {
        "name": "Wiki Updater",
        "script": "wiki/wiki_updater.py",
        "description": "Updates GitHub wiki"
    },
    "release": {
        "name": "Release Manager",
        "script": "release/release_manager.py",
        "description": "Generates changelog and release notes"
    },
    "pr": {
        "name": "PR Generator",
        "script": "release/pull_request_writer.py",
        "description": "Generates pull request descriptions"
    },
    "bugs": {
        "name": "Bug Prophet",
        "script": "predictive/predictive_bug_finder.py",
        "description": "Predicts potential bugs"
    },
    "security": {
        "name": "Security Analyzer",
        "script": "security/security_analyzer.py",
        "description": "Analyzes security vulnerabilities"
    },
    "deps": {
        "name": "Dependency Auditor",
        "script": "security/dependency_auditor.py",
        "description": "Audits package dependencies"
    },
    "lint": {
        "name": "Lint Master",
        "script": "lint/lint_refactor_agent.py",
        "description": "Refactors code for style"
    },
    "map": {
        "name": "Codebase Mapper",
        "script": "docs/map_generator.py",
        "description": "Generates codebase map"
    },
    "data_quality": {
        "name": "Data Quality",
        "script": "data_quality/data_quality_agent.py",
        "description": "Analyzes database quality"
    }
}

# Predefined pipelines
PIPELINES = {
    "full": ["pm", "sprint", "feature", "qa", "docs", "release"],
    "feature": ["pm", "feature", "qa"],
    "qa": ["qa", "bugs", "security"],
    "docs": ["docs", "wiki", "map"],
    "release": ["qa", "docs", "release", "pr"],
    "audit": ["security", "deps", "data_quality", "lint"],
    "review": ["bugs", "security", "lint", "ux"]
}


class PipelineOrchestrator:
    """Orchestrates multi-agent pipelines."""

    def __init__(self):
        self.results = {}
        self.start_time = None
        self.log_file = None

    def setup_logging(self):
        """Setup pipeline logging."""
        RESULTS_DIR.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = RESULTS_DIR / f"pipeline_log_{timestamp}.md"

        with open(self.log_file, "w") as f:
            f.write("# AI Pipeline Execution Log\n\n")
            f.write(f"Started: {datetime.now().isoformat()}\n\n")
            f.write("---\n\n")

    def log(self, message: str, level: str = "info"):
        """Log message to file and console."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = {"info": "ℹ️", "success": "✅", "error": "❌", "warning": "⚠️"}.get(level, "")

        console_msg = f"[{timestamp}] {prefix} {message}"
        print(console_msg)

        if self.log_file:
            with open(self.log_file, "a") as f:
                f.write(f"**[{timestamp}]** {message}\n\n")

    def run_agent(self, agent_key: str, args: list = None) -> dict:
        """Run a single agent."""
        if agent_key not in AGENTS:
            return {"success": False, "error": f"Unknown agent: {agent_key}"}

        agent = AGENTS[agent_key]
        script_path = SCRIPT_DIR / agent["script"]

        if not script_path.exists():
            return {"success": False, "error": f"Script not found: {script_path}"}

        self.log(f"Starting {agent['name']}...")

        cmd = [sys.executable, str(script_path)]
        if args:
            cmd.extend(args)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout
                cwd=SCRIPT_DIR
            )

            success = result.returncode == 0
            output = result.stdout + result.stderr

            if success:
                self.log(f"{agent['name']} completed successfully", "success")
            else:
                self.log(f"{agent['name']} failed with code {result.returncode}", "error")

            return {
                "success": success,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "output": output
            }

        except subprocess.TimeoutExpired:
            self.log(f"{agent['name']} timed out", "error")
            return {"success": False, "error": "Timeout"}

        except Exception as e:
            self.log(f"{agent['name']} error: {e}", "error")
            return {"success": False, "error": str(e)}

    def run_pipeline(self, pipeline_name: str, stop_on_error: bool = False) -> dict:
        """Run a predefined pipeline."""
        if pipeline_name not in PIPELINES:
            return {"success": False, "error": f"Unknown pipeline: {pipeline_name}"}

        agents = PIPELINES[pipeline_name]
        return self.run_agents(agents, stop_on_error)

    def run_agents(self, agents: list, stop_on_error: bool = False) -> dict:
        """Run a list of agents in sequence."""
        self.setup_logging()
        self.start_time = datetime.now()
        self.results = {}

        self.log(f"Pipeline started with {len(agents)} agents")
        self.log(f"Agents: {' → '.join(agents)}")

        success_count = 0
        error_count = 0

        for agent_key in agents:
            result = self.run_agent(agent_key)
            self.results[agent_key] = result

            if result.get("success"):
                success_count += 1
            else:
                error_count += 1
                if stop_on_error:
                    self.log("Pipeline stopped due to error", "warning")
                    break

        duration = (datetime.now() - self.start_time).total_seconds()

        summary = {
            "success": error_count == 0,
            "agents_run": len(self.results),
            "success_count": success_count,
            "error_count": error_count,
            "duration_seconds": duration,
            "results": self.results
        }

        self.save_summary(summary)
        return summary

    def save_summary(self, summary: dict):
        """Save pipeline summary."""
        # Save JSON
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_file = RESULTS_DIR / f"pipeline_summary_{timestamp}.json"

        # Simplify results for JSON
        json_summary = {
            "timestamp": timestamp,
            "success": summary["success"],
            "agents_run": summary["agents_run"],
            "success_count": summary["success_count"],
            "error_count": summary["error_count"],
            "duration_seconds": summary["duration_seconds"],
            "agents": {
                k: {"success": v.get("success"), "error": v.get("error")}
                for k, v in summary.get("results", {}).items()
            }
        }

        with open(json_file, "w") as f:
            json.dump(json_summary, f, indent=2)

        # Update log file
        if self.log_file:
            with open(self.log_file, "a") as f:
                f.write("\n---\n\n")
                f.write("## Pipeline Summary\n\n")
                f.write(f"- **Status:** {'✅ Success' if summary['success'] else '❌ Failed'}\n")
                f.write(f"- **Agents Run:** {summary['agents_run']}\n")
                f.write(f"- **Successful:** {summary['success_count']}\n")
                f.write(f"- **Failed:** {summary['error_count']}\n")
                f.write(f"- **Duration:** {summary['duration_seconds']:.1f}s\n")

        self.log(f"Summary saved to: {json_file}")


def print_help():
    """Print usage help."""
    print("""
CLAUDE-ORCHESTRATOR: AI Multi-Agent Pipeline

Usage:
  python orchestrator.py <pipeline>     Run a predefined pipeline
  python orchestrator.py <agent>        Run a single agent
  python orchestrator.py --list         List available agents and pipelines

Predefined Pipelines:
""")
    for name, agents in PIPELINES.items():
        print(f"  {name:12} → {' → '.join(agents)}")

    print("""
Available Agents:
""")
    for key, agent in AGENTS.items():
        print(f"  {key:14} {agent['name']:20} {agent['description']}")

    print("""
Examples:
  python orchestrator.py full           Run full PM → Eng → QA → Docs → Release
  python orchestrator.py feature        Run PM → Feature → QA
  python orchestrator.py qa             Run QA agents
  python orchestrator.py pm             Run only PRD generator
  python orchestrator.py pm sprint      Run PM then Sprint Planner
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

    orchestrator = PipelineOrchestrator()

    print("=" * 60)
    print("CLAUDE-ORCHESTRATOR: AI Multi-Agent Pipeline")
    print("=" * 60)

    # Check if it's a pipeline
    if len(args) == 1 and args[0] in PIPELINES:
        pipeline_name = args[0]
        print(f"\nRunning pipeline: {pipeline_name}")
        print(f"Agents: {' → '.join(PIPELINES[pipeline_name])}\n")

        summary = orchestrator.run_pipeline(pipeline_name)

    # Check if it's a single agent
    elif len(args) == 1 and args[0] in AGENTS:
        agent_key = args[0]
        print(f"\nRunning agent: {AGENTS[agent_key]['name']}\n")

        summary = orchestrator.run_agents([agent_key])

    # Multiple agents specified
    elif all(a in AGENTS for a in args):
        print(f"\nRunning agents: {' → '.join(args)}\n")
        summary = orchestrator.run_agents(args)

    else:
        print(f"Unknown pipeline or agent: {args}")
        print_help()
        return 1

    # Print final summary
    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)
    print(f"Status: {'✅ Success' if summary['success'] else '❌ Failed'}")
    print(f"Agents: {summary['success_count']}/{summary['agents_run']} successful")
    print(f"Duration: {summary['duration_seconds']:.1f}s")

    if orchestrator.log_file:
        print(f"\nLog: {orchestrator.log_file}")

    return 0 if summary["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
