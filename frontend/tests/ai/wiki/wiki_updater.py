#!/usr/bin/env python3
"""
CLAUDE-WIKI-UPDATER: AI Wiki Auto-Update Engine

Automatically updates GitHub Wiki pages based on:
- Recent code changes
- Architecture updates
- API evolution
- New features
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
You are CLAUDE-WIKI-UPDATER, an expert at maintaining GitHub Wiki documentation.

Your goals:
1. Update wiki articles based on code changes
2. Rewrite outdated documentation
3. Create new wiki sections when needed
4. Maintain consistent terminology across pages
5. Keep documentation in sync with codebase

Wiki Page Types:
- Home.md - Project overview and navigation
- Getting-Started.md - Quick start guide
- Installation.md - Detailed setup instructions
- Configuration.md - Environment and config options
- API-Reference.md - API endpoints documentation
- Architecture.md - System design overview
- Contributing.md - Contribution guidelines
- Troubleshooting.md - Common issues and solutions
- FAQ.md - Frequently asked questions

Standards:
- Use consistent markdown formatting
- Include links between related pages
- Add code examples with proper syntax highlighting
- Keep content up-to-date with latest changes
- Use clear, concise language

Output Format (JSON):
{
  "updates": [
    {
      "page": "Page-Name.md",
      "action": "create|update|delete",
      "reason": "Why this change is needed",
      "content": "Full page content..."
    }
  ],
  "summary": "Overall summary of changes",
  "new_pages_needed": ["..."],
  "deprecated_content": ["..."]
}
"""


def get_recent_changes() -> str:
    """Get recent git changes for context."""

    try:
        # Get recent commits
        result = subprocess.run(
            ["git", "log", "--oneline", "-20"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT
        )
        commits = result.stdout

        # Get changed files
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~10"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT
        )
        changed_files = result.stdout

        return f"Recent Commits:\n{commits}\n\nChanged Files:\n{changed_files}"

    except:
        return "Unable to get git history"


def read_existing_wiki() -> dict:
    """Read existing wiki pages if available."""

    wiki_pages = {}
    wiki_dir = PROJECT_ROOT / "wiki"

    # Check local wiki directory
    if wiki_dir.exists():
        for file in wiki_dir.glob("*.md"):
            try:
                wiki_pages[file.stem] = file.read_text()
            except:
                pass

    # Check docs directory as alternative
    docs_dir = PROJECT_ROOT / "docs"
    if docs_dir.exists():
        for file in docs_dir.glob("*.md"):
            if file.stem not in wiki_pages:
                try:
                    wiki_pages[file.stem] = file.read_text()
                except:
                    pass

    return wiki_pages


def read_documentation() -> str:
    """Read existing documentation for context."""

    docs = []

    doc_files = [
        PROJECT_ROOT / "README.md",
        PROJECT_ROOT / "DOCUMENTATION.md",
        PROJECT_ROOT / "docs" / "README.md",
    ]

    for file in doc_files:
        if file.exists():
            try:
                content = file.read_text()
                docs.append(f"## {file.name}\n{content[:3000]}")
            except:
                pass

    return "\n\n".join(docs)


def scan_api_routes() -> list:
    """Scan FastAPI routes for API documentation."""

    routes = []
    api_dir = PROJECT_ROOT / "backend" / "app" / "api" / "v1"

    if api_dir.exists():
        for file in api_dir.glob("*.py"):
            if not file.name.startswith("_"):
                try:
                    content = file.read_text()
                    # Extract routes
                    pattern = r'@\w+\.(get|post|put|patch|delete)\(["\']([^"\']+)["\'][^)]*\)'
                    matches = re.findall(pattern, content)
                    for method, path in matches:
                        routes.append({
                            "method": method.upper(),
                            "path": path,
                            "file": file.name
                        })
                except:
                    pass

    return routes


def update_wiki(existing_wiki: dict, recent_changes: str, docs: str, routes: list) -> dict:
    """Generate wiki updates with Claude."""

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {"error": "ANTHROPIC_API_KEY not set"}

    print("Analyzing codebase and generating wiki updates...")

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=12000,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"""
Update the GitHub Wiki for ABVTrends based on current codebase state.

## Recent Code Changes
{recent_changes}

## Existing Wiki Pages
{json.dumps(list(existing_wiki.keys()), indent=2)}

## Existing Documentation
{docs[:5000]}

## API Routes
{json.dumps(routes, indent=2)}

## Project Info
ABVTrends is an AI-powered alcohol trend forecasting platform featuring:
- Real-time trend tracking and scoring
- AI-driven predictions
- Web scraping from multiple sources
- Interactive dashboard

Please:
1. Analyze what wiki pages need updating
2. Create new pages for missing topics
3. Update existing pages with new information
4. Ensure consistency across all pages

Return updates as JSON.
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


def save_wiki_updates(updates: dict):
    """Save wiki updates to files."""

    RESULTS_DIR.mkdir(exist_ok=True)
    wiki_dir = PROJECT_ROOT / "wiki"
    wiki_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    saved_pages = []

    if "updates" in updates:
        for update in updates["updates"]:
            page_name = update.get("page", "Unknown.md")
            action = update.get("action", "update")
            content = update.get("content", "")

            if content and action != "delete":
                # Save to wiki directory
                wiki_file = wiki_dir / page_name
                with open(wiki_file, "w") as f:
                    f.write(content)
                saved_pages.append(str(wiki_file))
                print(f"  [{action.upper()}] {page_name}")

    # Save summary report
    report_file = RESULTS_DIR / "wiki_updates.md"
    with open(report_file, "w") as f:
        f.write(f"# Wiki Update Report\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")

        if "summary" in updates:
            f.write("## Summary\n")
            f.write(updates["summary"])
            f.write("\n\n")

        if "updates" in updates:
            f.write("## Updates Made\n\n")
            for update in updates["updates"]:
                f.write(f"### {update.get('page', 'Unknown')}\n")
                f.write(f"- **Action:** {update.get('action', 'N/A')}\n")
                f.write(f"- **Reason:** {update.get('reason', 'N/A')}\n\n")

        if "new_pages_needed" in updates:
            f.write("## New Pages Recommended\n")
            for page in updates["new_pages_needed"]:
                f.write(f"- {page}\n")

        if "deprecated_content" in updates:
            f.write("\n## Deprecated Content\n")
            for item in updates["deprecated_content"]:
                f.write(f"- {item}\n")

        if "raw_response" in updates:
            f.write("\n## Raw Response\n\n")
            f.write(updates["raw_response"])

    print(f"\nReport saved to: {report_file}")

    # Save JSON
    json_file = RESULTS_DIR / f"wiki_updates_{timestamp}.json"
    with open(json_file, "w") as f:
        json.dump(updates, f, indent=2)

    return saved_pages


def main():
    """Main execution flow."""

    print("=" * 60)
    print("CLAUDE-WIKI-UPDATER: AI Wiki Auto-Update Engine")
    print("=" * 60)

    # Gather context
    print("\nGathering project context...")

    recent_changes = get_recent_changes()
    existing_wiki = read_existing_wiki()
    docs = read_documentation()
    routes = scan_api_routes()

    print(f"  Existing wiki pages: {len(existing_wiki)}")
    print(f"  API routes found: {len(routes)}")

    # Generate updates
    updates = update_wiki(existing_wiki, recent_changes, docs, routes)

    if "error" in updates:
        print(f"\nError: {updates['error']}")
        return 1

    # Save updates
    print("\nSaving wiki updates...")
    saved_pages = save_wiki_updates(updates)

    print("\n" + "=" * 60)
    print("WIKI UPDATE COMPLETE")
    print("=" * 60)
    print(f"Updated {len(saved_pages)} wiki pages")

    if "summary" in updates:
        print(f"\nSummary: {updates['summary']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
