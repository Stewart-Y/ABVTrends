#!/usr/bin/env python3
"""
CLAUDE-RELEASE-MANAGER: AI Release Manager

Automatically generates:
- CHANGELOG.md entries
- GitHub release notes
- Semantic version bumps
- Marketing-friendly summaries
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
You are CLAUDE-RELEASE-MANAGER, an expert in software release management.

Your responsibilities:
1. Analyze git commits since the last tag
2. Categorize changes using Conventional Commits:
   - feat: New features
   - fix: Bug fixes
   - perf: Performance improvements
   - docs: Documentation changes
   - refactor: Code refactoring
   - test: Test additions/changes
   - chore: Maintenance tasks
   - ci: CI/CD changes
3. Determine semantic version bump:
   - MAJOR: Breaking changes
   - MINOR: New features (backward compatible)
   - PATCH: Bug fixes (backward compatible)
4. Generate a professional CHANGELOG entry
5. Create GitHub release notes (markdown)
6. Produce a marketing-friendly summary

Output Format (JSON):
{
  "version_bump": "major|minor|patch",
  "new_version": "X.Y.Z",
  "changelog": {
    "added": ["..."],
    "changed": ["..."],
    "fixed": ["..."],
    "deprecated": ["..."],
    "removed": ["..."],
    "security": ["..."]
  },
  "release_notes": "Full markdown release notes...",
  "marketing_summary": "User-friendly summary...",
  "breaking_changes": ["..."],
  "highlights": ["..."]
}
"""


def get_current_version() -> str:
    """Get current version from git tags or package.json."""

    # Try git tags first
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT
        )
        if result.returncode == 0:
            tag = result.stdout.strip()
            # Extract version number
            version_match = re.search(r'(\d+\.\d+\.\d+)', tag)
            if version_match:
                return version_match.group(1)
    except:
        pass

    # Try package.json
    package_json = PROJECT_ROOT / "frontend" / "package.json"
    if package_json.exists():
        try:
            data = json.load(open(package_json))
            return data.get("version", "0.0.0")
        except:
            pass

    return "0.0.0"


def get_git_commits_since_tag() -> str:
    """Get all commits since the last tag."""

    try:
        # Get last tag
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT
        )

        if result.returncode == 0:
            last_tag = result.stdout.strip()
            commit_range = f"{last_tag}..HEAD"
        else:
            # No tags, get all commits
            commit_range = "HEAD"

        # Get commit messages
        result = subprocess.run(
            ["git", "log", commit_range, "--pretty=format:%h|%s|%an|%ad", "--date=short"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT
        )

        return result.stdout

    except Exception as e:
        print(f"Error getting git commits: {e}")
        return ""


def get_changed_files() -> list:
    """Get list of changed files since last tag."""

    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT
        )

        if result.returncode == 0:
            last_tag = result.stdout.strip()
            commit_range = f"{last_tag}..HEAD"
        else:
            commit_range = "HEAD~20..HEAD"  # Last 20 commits

        result = subprocess.run(
            ["git", "diff", "--name-only", commit_range],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT
        )

        return result.stdout.strip().split("\n") if result.stdout.strip() else []

    except:
        return []


def generate_release(commits: str, current_version: str, changed_files: list) -> dict:
    """Generate release notes with Claude."""

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {"error": "ANTHROPIC_API_KEY not set"}

    if not commits.strip():
        return {"error": "No commits found since last release"}

    print("Analyzing commits and generating release notes...")

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"""
Generate release notes for ABVTrends based on these commits.

## Current Version
{current_version}

## Commits Since Last Release
Format: hash|message|author|date

{commits}

## Changed Files
{json.dumps(changed_files[:50], indent=2)}

Please:
1. Categorize all changes
2. Determine the appropriate version bump
3. Generate comprehensive release notes
4. Create a marketing-friendly summary
5. Highlight breaking changes if any

Return your response as JSON.
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


def update_changelog(release_data: dict):
    """Update or create CHANGELOG.md."""

    changelog_path = PROJECT_ROOT / "CHANGELOG.md"

    # Generate changelog entry
    date_str = datetime.now().strftime("%Y-%m-%d")
    version = release_data.get("new_version", "Unreleased")

    entry = f"\n\n## [{version}] - {date_str}\n\n"

    changelog = release_data.get("changelog", {})

    sections = [
        ("Added", changelog.get("added", [])),
        ("Changed", changelog.get("changed", [])),
        ("Fixed", changelog.get("fixed", [])),
        ("Deprecated", changelog.get("deprecated", [])),
        ("Removed", changelog.get("removed", [])),
        ("Security", changelog.get("security", [])),
    ]

    for section_name, items in sections:
        if items:
            entry += f"### {section_name}\n"
            for item in items:
                entry += f"- {item}\n"
            entry += "\n"

    # Read existing changelog or create new
    if changelog_path.exists():
        existing = changelog_path.read_text()
        # Insert after header
        header_match = re.search(r'(# Changelog.*?\n\n)', existing, re.DOTALL)
        if header_match:
            new_content = existing[:header_match.end()] + entry + existing[header_match.end():]
        else:
            new_content = existing + entry
    else:
        new_content = f"""# Changelog

All notable changes to ABVTrends will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
{entry}"""

    with open(changelog_path, "w") as f:
        f.write(new_content)

    print(f"Updated CHANGELOG.md with version {version}")


def save_release_notes(release_data: dict):
    """Save release notes to results directory."""

    RESULTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save JSON
    json_file = RESULTS_DIR / f"release_{timestamp}.json"
    with open(json_file, "w") as f:
        json.dump(release_data, f, indent=2)

    # Save markdown release notes
    release_notes = release_data.get("release_notes", "")
    if release_notes:
        notes_file = RESULTS_DIR / "release_notes.md"
        with open(notes_file, "w") as f:
            f.write(f"# Release {release_data.get('new_version', 'Unreleased')}\n\n")
            f.write(release_notes)
        print(f"Release notes saved to: {notes_file}")

    # Save marketing summary
    marketing = release_data.get("marketing_summary", "")
    if marketing:
        marketing_file = RESULTS_DIR / "release_marketing.md"
        with open(marketing_file, "w") as f:
            f.write(f"# What's New in ABVTrends {release_data.get('new_version', '')}\n\n")
            f.write(marketing)
        print(f"Marketing summary saved to: {marketing_file}")


def create_git_tag(version: str, dry_run: bool = True):
    """Create a git tag for the release."""

    if dry_run:
        print(f"\n[DRY RUN] Would create tag: v{version}")
        return

    try:
        subprocess.run(
            ["git", "tag", "-a", f"v{version}", "-m", f"Release v{version}"],
            check=True,
            cwd=PROJECT_ROOT
        )
        print(f"Created tag: v{version}")
    except Exception as e:
        print(f"Error creating tag: {e}")


def main():
    """Main execution flow."""

    print("=" * 60)
    print("CLAUDE-RELEASE-MANAGER: AI Release Manager")
    print("=" * 60)

    # Parse arguments
    create_tag = "--create-tag" in sys.argv
    update_changelog_flag = "--update-changelog" in sys.argv

    # Get current state
    current_version = get_current_version()
    print(f"\nCurrent version: {current_version}")

    commits = get_git_commits_since_tag()
    changed_files = get_changed_files()

    print(f"Commits to analyze: {len(commits.splitlines())}")
    print(f"Changed files: {len(changed_files)}")

    if not commits.strip():
        print("\nNo new commits since last release")
        return 0

    # Generate release
    release_data = generate_release(commits, current_version, changed_files)

    if "error" in release_data:
        print(f"\nError: {release_data['error']}")
        return 1

    # Display results
    print("\n" + "=" * 60)
    print("RELEASE SUMMARY")
    print("=" * 60)

    if "version_bump" in release_data:
        print(f"Version bump: {release_data['version_bump'].upper()}")
        print(f"New version: {release_data.get('new_version', 'N/A')}")

    if "highlights" in release_data:
        print("\nHighlights:")
        for highlight in release_data["highlights"]:
            print(f"  - {highlight}")

    if "breaking_changes" in release_data and release_data["breaking_changes"]:
        print("\n⚠️  Breaking Changes:")
        for change in release_data["breaking_changes"]:
            print(f"  - {change}")

    # Save release notes
    save_release_notes(release_data)

    # Update changelog if requested
    if update_changelog_flag:
        update_changelog(release_data)

    # Create tag if requested
    if create_tag:
        version = release_data.get("new_version")
        if version:
            create_git_tag(version, dry_run=False)

    print("\n" + "=" * 60)
    print("Release preparation complete!")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
