#!/usr/bin/env python3
"""
CLAUDE-PM: AI Product Manager

Generates:
- Product Requirements Documents (PRDs)
- User stories with acceptance criteria
- User personas and flows
- Technical specifications
- Release criteria
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
You are CLAUDE-PM, an expert Product Manager with 15+ years experience.

You create comprehensive product documentation including:

1. **Product Requirements Document (PRD)**
   - Executive summary
   - Problem statement
   - Goals and success metrics
   - User personas
   - User flows
   - Feature requirements
   - Non-functional requirements
   - Dependencies and risks

2. **User Stories**
   - Epic breakdown
   - Story format: As a [user], I want [action], so that [benefit]
   - Acceptance criteria (Given/When/Then)
   - Story points estimate
   - Priority (P0-P3)

3. **Technical Specifications**
   - System architecture considerations
   - Data model requirements
   - API contract requirements
   - Performance requirements
   - Security requirements

4. **Release Criteria**
   - MVP definition
   - Feature flags
   - Rollout plan
   - Success metrics
   - Rollback criteria

ABVTrends Context:
- AI-powered alcohol trend forecasting platform
- Users: beverage buyers, distributors, bar owners, enthusiasts
- Core features: trend tracking, scoring, forecasting, discovery
- Tech: FastAPI + PostgreSQL + Next.js

Output Format: Well-structured markdown with clear sections.
"""


def read_project_context() -> str:
    """Read project context for better PRDs."""

    context_parts = []

    # Read README
    readme = PROJECT_ROOT / "README.md"
    if readme.exists():
        try:
            content = readme.read_text()[:3000]
            context_parts.append(f"## Project README\n{content}")
        except:
            pass

    # Read existing features
    api_dir = PROJECT_ROOT / "backend" / "app" / "api" / "v1"
    if api_dir.exists():
        features = []
        for file in api_dir.glob("*.py"):
            if file.name != "__init__.py":
                features.append(file.stem)
        if features:
            context_parts.append(f"## Existing Features\n{', '.join(features)}")

    # Read models
    models_dir = PROJECT_ROOT / "backend" / "app" / "models"
    if models_dir.exists():
        models = []
        for file in models_dir.glob("*.py"):
            if file.name != "__init__.py":
                models.append(file.stem)
        if models:
            context_parts.append(f"## Data Models\n{', '.join(models)}")

    return "\n\n".join(context_parts)


def generate_prd(idea: str) -> dict:
    """Generate PRD from product idea."""

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {"error": "ANTHROPIC_API_KEY not set"}

    print("Generating PRD with Claude...")

    context = read_project_context()

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=12000,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"""
Create a comprehensive PRD for the following product idea/feature.

## Product Idea
{idea}

## Project Context
{context}

Please generate:
1. Full PRD with all sections
2. User stories with acceptance criteria
3. Technical specifications
4. Release criteria
5. Success metrics

Format as clean markdown.
"""
                }
            ]
        )

        content = response.content[0].text
        return {"prd": content}

    except Exception as e:
        return {"error": str(e)}


def extract_user_stories(prd_content: str) -> list:
    """Extract user stories from PRD."""

    stories = []

    # Pattern for user stories
    story_pattern = r'As a ([^,]+), I want ([^,]+), so that ([^.\n]+)'
    matches = re.findall(story_pattern, prd_content, re.IGNORECASE)

    for user, action, benefit in matches:
        stories.append({
            "user": user.strip(),
            "action": action.strip(),
            "benefit": benefit.strip()
        })

    return stories


def save_prd(result: dict, idea: str):
    """Save PRD to files."""

    RESULTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save main PRD
    prd_file = RESULTS_DIR / f"prd_{timestamp}.md"
    with open(prd_file, "w") as f:
        f.write(f"# Product Requirements Document\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")
        f.write("---\n\n")
        f.write(result.get("prd", ""))

    print(f"PRD saved to: {prd_file}")

    # Also save as latest
    latest_file = RESULTS_DIR / "prd_latest.md"
    with open(latest_file, "w") as f:
        f.write(f"# Product Requirements Document\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")
        f.write("---\n\n")
        f.write(result.get("prd", ""))

    # Extract and save user stories
    stories = extract_user_stories(result.get("prd", ""))
    if stories:
        stories_file = RESULTS_DIR / f"user_stories_{timestamp}.json"
        with open(stories_file, "w") as f:
            json.dump({
                "timestamp": timestamp,
                "idea": idea,
                "stories": stories
            }, f, indent=2)
        print(f"User stories saved to: {stories_file}")

    # Save idea for reference
    idea_file = SCRIPT_DIR / "idea.txt"
    with open(idea_file, "w") as f:
        f.write(idea)

    return prd_file


def main():
    """Main execution flow."""

    print("=" * 60)
    print("CLAUDE-PM: AI Product Manager")
    print("=" * 60)

    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    RESULTS_DIR.mkdir(exist_ok=True)

    # Check for idea file
    idea_file = SCRIPT_DIR / "idea.txt"

    if args:
        idea = " ".join(args)
    elif idea_file.exists():
        idea = idea_file.read_text().strip()
    else:
        print("\nUsage:")
        print("  python prd_generator.py 'Your product idea here'")
        print("  python prd_generator.py  # reads from idea.txt")
        print("\nCreate idea.txt with your product idea:")
        print(f"  {idea_file}")

        # Create sample idea file
        with open(idea_file, "w") as f:
            f.write("""# Example Product Idea
# Replace this with your actual feature/product idea

Add a social sharing feature where users can share their trend discoveries with friends, create "trend lists" like playlists, and follow other users to see what they're tracking.

## Goals
- Increase user engagement
- Drive viral growth
- Build community around trend discovery
""")
        print(f"\nCreated sample idea.txt at: {idea_file}")
        return 1

    print(f"\nProduct Idea:\n{idea[:200]}...")

    # Generate PRD
    result = generate_prd(idea)

    if "error" in result:
        print(f"\nError: {result['error']}")
        return 1

    # Save PRD
    prd_file = save_prd(result, idea)

    # Print summary
    print("\n" + "=" * 60)
    print("PRD GENERATION COMPLETE")
    print("=" * 60)

    stories = extract_user_stories(result.get("prd", ""))
    print(f"User stories extracted: {len(stories)}")
    print(f"\nPRD saved to: {prd_file}")

    if stories:
        print("\nTop User Stories:")
        for i, story in enumerate(stories[:5], 1):
            print(f"  {i}. As a {story['user']}, I want {story['action'][:50]}...")

    return 0


if __name__ == "__main__":
    sys.exit(main())
