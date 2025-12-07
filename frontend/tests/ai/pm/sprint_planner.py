#!/usr/bin/env python3
"""
CLAUDE-SPRINT-MASTER: AI Sprint Planner

Generates:
- 2-week sprint plans
- Story point estimates
- Task breakdowns
- Dependencies mapping
- Risk analysis
- QA test plans
"""

import os
import sys
import re
import json
from datetime import datetime, timedelta
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
You are CLAUDE-SPRINT-MASTER, an expert Agile coach and sprint planner.

You create comprehensive sprint plans including:

1. **Sprint Overview**
   - Sprint goal
   - Duration (2 weeks)
   - Start/end dates
   - Team capacity
   - Velocity target

2. **Backlog Prioritization**
   - P0 (Must have) items
   - P1 (Should have) items
   - P2 (Nice to have) items
   - Items deferred to next sprint

3. **Story Breakdown**
   For each story:
   - Story ID
   - Title
   - Description
   - Story points (1, 2, 3, 5, 8, 13)
   - Priority (P0/P1/P2)
   - Assignee type (Frontend/Backend/Full-stack)
   - Tasks breakdown
   - Definition of Done
   - Dependencies

4. **Task Breakdown**
   For each task:
   - Task ID
   - Description
   - Estimated hours
   - Blocked by (dependencies)

5. **Dependencies Graph**
   - Which stories block others
   - External dependencies
   - Integration points

6. **Risk Analysis**
   - Technical risks
   - Resource risks
   - Timeline risks
   - Mitigation strategies

7. **QA Test Plan**
   - Test cases for each story
   - Integration test requirements
   - E2E test scenarios
   - Performance test needs

8. **Sprint Calendar**
   - Day-by-day plan
   - Ceremonies (standup, review, retro)
   - Key milestones

ABVTrends Context:
- Small team (2-3 developers)
- Typical velocity: 20-30 story points/sprint
- Tech: FastAPI, PostgreSQL, Next.js, Playwright

Output Format: Structured markdown with tables and clear sections.
"""


def read_backlog() -> str:
    """Read backlog from file."""

    backlog_file = SCRIPT_DIR / "backlog.txt"
    if backlog_file.exists():
        return backlog_file.read_text()

    # Try to read from PRD
    prd_file = RESULTS_DIR / "prd_latest.md"
    if prd_file.exists():
        return prd_file.read_text()

    return ""


def get_team_context() -> dict:
    """Get team and project context."""

    context = {
        "team_size": 2,
        "velocity": 25,
        "sprint_duration": 14,
        "tech_stack": "FastAPI + PostgreSQL + Next.js"
    }

    # Count recent commits for velocity estimate
    try:
        import subprocess
        result = subprocess.run(
            ["git", "log", "--oneline", "--since=2 weeks ago"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT
        )
        commit_count = len(result.stdout.strip().split("\n"))
        context["recent_commits"] = commit_count
    except:
        pass

    return context


def plan_sprint(backlog: str) -> dict:
    """Generate sprint plan from backlog."""

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {"error": "ANTHROPIC_API_KEY not set"}

    print("Planning sprint with Claude...")

    team_context = get_team_context()
    start_date = datetime.now()
    end_date = start_date + timedelta(days=14)

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=12000,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"""
Create a 2-week sprint plan for the following backlog.

## Sprint Dates
- Start: {start_date.strftime('%Y-%m-%d')}
- End: {end_date.strftime('%Y-%m-%d')}

## Team Context
- Team size: {team_context['team_size']} developers
- Target velocity: {team_context['velocity']} story points
- Tech stack: {team_context['tech_stack']}

## Backlog Items
{backlog}

Please generate:
1. Sprint goal and overview
2. Prioritized backlog with story points
3. Detailed task breakdown for each story
4. Dependencies graph
5. Risk analysis
6. QA test plan
7. Sprint calendar with milestones

Format as clean markdown with tables.
"""
                }
            ]
        )

        content = response.content[0].text
        return {
            "sprint_plan": content,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        }

    except Exception as e:
        return {"error": str(e)}


def extract_stories(sprint_plan: str) -> list:
    """Extract stories from sprint plan."""

    stories = []

    # Pattern for story points
    story_pattern = r'(?:Story|US|STORY)[-\s]*(\d+)[:\s]*([^\n]+?)[\s]*[|\(](\d+)\s*(?:points?|pts?|SP)'
    matches = re.findall(story_pattern, sprint_plan, re.IGNORECASE)

    for story_id, title, points in matches:
        stories.append({
            "id": f"US-{story_id}",
            "title": title.strip(),
            "points": int(points)
        })

    return stories


def save_sprint_plan(result: dict, backlog: str):
    """Save sprint plan to files."""

    RESULTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save main sprint plan
    plan_file = RESULTS_DIR / f"sprint_plan_{timestamp}.md"
    with open(plan_file, "w") as f:
        f.write(f"# Sprint Plan\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n")
        f.write(f"Sprint Period: {result.get('start_date', 'TBD')} to {result.get('end_date', 'TBD')}\n\n")
        f.write("---\n\n")
        f.write(result.get("sprint_plan", ""))

    print(f"Sprint plan saved to: {plan_file}")

    # Also save as latest
    latest_file = RESULTS_DIR / "sprint_plan.md"
    with open(latest_file, "w") as f:
        f.write(f"# Sprint Plan\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n")
        f.write(f"Sprint Period: {result.get('start_date', 'TBD')} to {result.get('end_date', 'TBD')}\n\n")
        f.write("---\n\n")
        f.write(result.get("sprint_plan", ""))

    # Extract and save stories as JSON for tooling
    stories = extract_stories(result.get("sprint_plan", ""))
    if stories:
        stories_file = RESULTS_DIR / f"sprint_stories_{timestamp}.json"
        with open(stories_file, "w") as f:
            json.dump({
                "timestamp": timestamp,
                "start_date": result.get("start_date"),
                "end_date": result.get("end_date"),
                "total_points": sum(s["points"] for s in stories),
                "stories": stories
            }, f, indent=2)
        print(f"Sprint stories saved to: {stories_file}")

    return plan_file


def main():
    """Main execution flow."""

    print("=" * 60)
    print("CLAUDE-SPRINT-MASTER: AI Sprint Planner")
    print("=" * 60)

    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    RESULTS_DIR.mkdir(exist_ok=True)

    # Check for backlog file
    backlog_file = SCRIPT_DIR / "backlog.txt"

    if args:
        backlog = " ".join(args)
    elif backlog_file.exists():
        backlog = backlog_file.read_text().strip()
    else:
        # Try PRD as fallback
        backlog = read_backlog()

        if not backlog:
            print("\nUsage:")
            print("  python sprint_planner.py 'Your backlog items here'")
            print("  python sprint_planner.py  # reads from backlog.txt")
            print("\nCreate backlog.txt with your backlog items:")
            print(f"  {backlog_file}")

            # Create sample backlog file
            with open(backlog_file, "w") as f:
                f.write("""# Sprint Backlog
# List your backlog items below

## High Priority (P0)
1. Implement user watchlist feature
   - Add/remove products from watchlist
   - Persist watchlist to database
   - Show watchlist on dashboard

2. Add trend score alerts
   - Notify when score increases by 15+
   - Email notification system
   - In-app notification badge

## Medium Priority (P1)
3. Improve search functionality
   - Add filters by category
   - Add filters by trend tier
   - Search by brand

4. Mobile responsive design
   - Dashboard mobile layout
   - Trends table mobile view
   - Product detail mobile view

## Low Priority (P2)
5. Add data export feature
   - Export to CSV
   - Export to PDF report

6. Dark mode support
   - Theme toggle
   - Persist preference
""")
            print(f"\nCreated sample backlog.txt at: {backlog_file}")
            return 1

    print(f"\nBacklog Preview:\n{backlog[:300]}...")

    # Plan sprint
    result = plan_sprint(backlog)

    if "error" in result:
        print(f"\nError: {result['error']}")
        return 1

    # Save sprint plan
    plan_file = save_sprint_plan(result, backlog)

    # Print summary
    print("\n" + "=" * 60)
    print("SPRINT PLANNING COMPLETE")
    print("=" * 60)

    stories = extract_stories(result.get("sprint_plan", ""))
    total_points = sum(s["points"] for s in stories)

    print(f"Sprint: {result.get('start_date', 'TBD')} to {result.get('end_date', 'TBD')}")
    print(f"Stories planned: {len(stories)}")
    print(f"Total story points: {total_points}")
    print(f"\nSprint plan saved to: {plan_file}")

    if stories:
        print("\nPlanned Stories:")
        for story in stories[:10]:
            print(f"  [{story['points']} pts] {story['id']}: {story['title'][:50]}...")

    return 0


if __name__ == "__main__":
    sys.exit(main())
