#!/usr/bin/env python3
"""
CLAUDE-PR-BOT: AI Pull Request Generator

Generates comprehensive pull request content:
- Title and description
- Code diff explanation
- Testing checklist
- Review guidelines
- Suggested labels
- Breaking changes warnings
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
You are CLAUDE-PR-BOT, an expert at creating comprehensive pull request descriptions.

You generate:

1. **PR Title**
   - Conventional commit format (feat:, fix:, docs:, etc.)
   - Clear, concise description
   - Issue reference if applicable

2. **Summary**
   - What changes were made
   - Why they were made
   - Key implementation details

3. **Changes**
   - File-by-file breakdown
   - Code diff explanation
   - New features/fixes

4. **Testing**
   - What was tested
   - Test commands to run
   - Testing checklist

5. **Review Checklist**
   - Code quality items
   - Security considerations
   - Performance impacts

6. **Labels**
   - Suggested GitHub labels
   - Type (feature, bug, docs, etc.)
   - Priority/size

7. **Breaking Changes**
   - API changes
   - Database migrations
   - Config changes

8. **Related Issues**
   - Closes/fixes references
   - Related PRs

Output Format:
Return a well-structured markdown document ready to paste as PR description.

Include:
- [ ] Checkboxes for testing items
- Tables for file changes
- Code snippets where helpful
- Clear section headers
"""


def get_git_diff(base_branch: str = "main") -> str:
    """Get git diff from base branch."""

    try:
        # Get diff
        result = subprocess.run(
            ["git", "diff", f"{base_branch}...HEAD"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT
        )
        return result.stdout

    except Exception as e:
        return f"Error getting diff: {e}"


def get_staged_diff() -> str:
    """Get staged changes diff."""

    try:
        result = subprocess.run(
            ["git", "diff", "--cached"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT
        )
        return result.stdout if result.stdout else get_working_diff()

    except Exception as e:
        return f"Error getting staged diff: {e}"


def get_working_diff() -> str:
    """Get working directory changes diff."""

    try:
        result = subprocess.run(
            ["git", "diff"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT
        )
        return result.stdout

    except Exception as e:
        return f"Error getting diff: {e}"


def get_commit_history(base_branch: str = "main") -> str:
    """Get commit history from base branch."""

    try:
        result = subprocess.run(
            ["git", "log", f"{base_branch}..HEAD", "--oneline", "--no-merges"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT
        )
        return result.stdout

    except Exception as e:
        return f"Error getting commits: {e}"


def get_changed_files(base_branch: str = "main") -> list:
    """Get list of changed files."""

    try:
        result = subprocess.run(
            ["git", "diff", "--name-status", f"{base_branch}...HEAD"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT
        )

        files = []
        for line in result.stdout.strip().split("\n"):
            if line:
                parts = line.split("\t")
                if len(parts) >= 2:
                    files.append({
                        "status": parts[0],
                        "file": parts[1]
                    })

        return files

    except Exception as e:
        return []


def get_current_branch() -> str:
    """Get current branch name."""

    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT
        )
        return result.stdout.strip()

    except Exception:
        return "unknown"


def generate_pr_content(diff: str, commits: str, changed_files: list, branch: str) -> dict:
    """Generate PR content with Claude."""

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {"error": "ANTHROPIC_API_KEY not set"}

    if not diff or diff.startswith("Error"):
        return {"error": "No diff available"}

    print("Generating PR content with Claude...")

    # Summarize changed files
    files_summary = ""
    for f in changed_files[:30]:
        status_map = {"A": "Added", "M": "Modified", "D": "Deleted", "R": "Renamed"}
        status = status_map.get(f["status"], f["status"])
        files_summary += f"- {status}: `{f['file']}`\n"

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"""
Generate a pull request description for the following changes.

## Branch
{branch}

## Changed Files ({len(changed_files)} files)
{files_summary}

## Commits
{commits[:2000]}

## Diff
{diff[:30000]}

Please generate:
1. PR title (conventional commit format)
2. Summary section
3. Changes breakdown
4. Testing checklist
5. Review checklist
6. Suggested labels
7. Breaking changes (if any)

Format as markdown ready to paste into GitHub PR description.
"""
                }
            ]
        )

        content = response.content[0].text

        # Extract title if present
        title_match = re.search(r'^#?\s*(?:PR Title:?\s*)?(.+?)(?:\n|$)', content, re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else f"feat: {branch}"

        return {
            "title": title,
            "body": content,
            "branch": branch,
            "files_changed": len(changed_files)
        }

    except Exception as e:
        return {"error": str(e)}


def save_pr_content(result: dict):
    """Save PR content to files."""

    RESULTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save markdown
    pr_file = RESULTS_DIR / f"pull_request_{timestamp}.md"
    with open(pr_file, "w") as f:
        f.write(f"# {result.get('title', 'Pull Request')}\n\n")
        f.write(f"Branch: `{result.get('branch', 'unknown')}`\n")
        f.write(f"Files Changed: {result.get('files_changed', 0)}\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")
        f.write("---\n\n")
        f.write(result.get("body", ""))

    print(f"PR content saved to: {pr_file}")

    # Also save as latest
    latest_file = RESULTS_DIR / "pull_request.md"
    with open(latest_file, "w") as f:
        f.write(f"# {result.get('title', 'Pull Request')}\n\n")
        f.write(result.get("body", ""))

    # Save JSON
    json_file = RESULTS_DIR / f"pull_request_{timestamp}.json"
    with open(json_file, "w") as f:
        json.dump({
            "timestamp": timestamp,
            "title": result.get("title"),
            "branch": result.get("branch"),
            "files_changed": result.get("files_changed"),
            "body_length": len(result.get("body", ""))
        }, f, indent=2)

    return pr_file


def create_github_pr(result: dict, base_branch: str = "main") -> bool:
    """Create PR using GitHub CLI."""

    try:
        # Check if gh is available
        check = subprocess.run(["gh", "--version"], capture_output=True)
        if check.returncode != 0:
            print("GitHub CLI (gh) not found. Install from: https://cli.github.com/")
            return False

        title = result.get("title", "Pull Request")
        body = result.get("body", "")

        # Create PR
        result = subprocess.run(
            ["gh", "pr", "create",
             "--title", title,
             "--body", body,
             "--base", base_branch],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT
        )

        if result.returncode == 0:
            print(f"PR created: {result.stdout.strip()}")
            return True
        else:
            print(f"Failed to create PR: {result.stderr}")
            return False

    except Exception as e:
        print(f"Error creating PR: {e}")
        return False


def main():
    """Main execution flow."""

    print("=" * 60)
    print("CLAUDE-PR-BOT: AI Pull Request Generator")
    print("=" * 60)

    # Parse arguments
    create_pr = "--create" in sys.argv
    base_branch = "main"

    for i, arg in enumerate(sys.argv):
        if arg == "--base" and i + 1 < len(sys.argv):
            base_branch = sys.argv[i + 1]

    RESULTS_DIR.mkdir(exist_ok=True)

    # Get current branch
    branch = get_current_branch()
    print(f"\nBranch: {branch}")
    print(f"Base: {base_branch}")

    # Get git information
    print("\nGathering git information...")

    print("  Getting diff...")
    diff = get_git_diff(base_branch)
    if not diff:
        diff = get_staged_diff()
    if not diff:
        diff = get_working_diff()

    print("  Getting commit history...")
    commits = get_commit_history(base_branch)

    print("  Getting changed files...")
    changed_files = get_changed_files(base_branch)
    print(f"  Found {len(changed_files)} changed files")

    if not diff or diff.startswith("Error"):
        print("\nNo changes found to generate PR for.")
        print("Make sure you have uncommitted changes or are on a feature branch.")
        return 1

    # Generate PR content
    result = generate_pr_content(diff, commits, changed_files, branch)

    if "error" in result:
        print(f"\nError: {result['error']}")
        return 1

    # Save PR content
    pr_file = save_pr_content(result)

    # Print summary
    print("\n" + "=" * 60)
    print("PR CONTENT GENERATED")
    print("=" * 60)
    print(f"Title: {result.get('title', 'N/A')}")
    print(f"Files: {result.get('files_changed', 0)}")
    print(f"\nContent saved to: {pr_file}")

    # Create PR if requested
    if create_pr:
        print("\nCreating PR on GitHub...")
        if create_github_pr(result, base_branch):
            print("PR created successfully!")
        else:
            print("Failed to create PR. You can copy the content manually.")
    else:
        print("\nTo create PR on GitHub:")
        print(f"  python pull_request_writer.py --create --base {base_branch}")
        print("\nOr copy content from:")
        print(f"  {RESULTS_DIR / 'pull_request.md'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
