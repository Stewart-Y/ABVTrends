#!/usr/bin/env python3
"""
CLAUDE-DOC-WRITER: AI Documentation Writer

Generates comprehensive documentation:
- README.md
- Architecture documentation
- API reference from FastAPI routes
- Developer onboarding guides
- Testing strategy documentation
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
You are CLAUDE-DOC-WRITER, an expert technical writer for software projects.

You write:
1. README.md - Project overview, setup instructions, usage
2. ARCHITECTURE.md - System design, component interactions
3. API.md - API reference from FastAPI routes
4. DEVELOPER_GUIDE.md - Onboarding, contribution guidelines
5. TESTING.md - Testing strategy and guidelines

Documentation Standards:
- Clear, concise language
- Include code examples
- Use ASCII diagrams for architecture
- Follow industry best practices
- Include table of contents for long docs
- Add badges where appropriate

ABVTrends Context:
- Alcohol trend forecasting platform
- FastAPI backend with PostgreSQL
- Next.js frontend with TypeScript
- AI-powered trend analysis
- Web scraping for data collection

Output Format:
Return a JSON object with documentation sections:
{
  "readme": "Full README content...",
  "architecture": "Architecture doc content...",
  "api": "API reference content...",
  "developer_guide": "Developer guide content...",
  "testing": "Testing guide content..."
}
"""


def scan_project_structure() -> dict:
    """Scan project structure and gather metadata."""

    structure = {
        "backend": {"files": [], "routes": [], "models": [], "services": []},
        "frontend": {"files": [], "pages": [], "components": []},
        "config_files": [],
        "doc_files": []
    }

    # Scan backend
    if BACKEND_DIR.exists():
        # API routes
        api_dir = BACKEND_DIR / "app" / "api" / "v1"
        if api_dir.exists():
            for file in api_dir.glob("*.py"):
                if not file.name.startswith("_"):
                    content = file.read_text()
                    routes = re.findall(r'@\w+\.(get|post|put|delete)\(["\']([^"\']+)', content)
                    structure["backend"]["routes"].extend([
                        {"method": m.upper(), "path": p, "file": file.name}
                        for m, p in routes
                    ])

        # Models
        models_dir = BACKEND_DIR / "app" / "models"
        if models_dir.exists():
            for file in models_dir.glob("*.py"):
                if not file.name.startswith("_"):
                    content = file.read_text()
                    classes = re.findall(r'class\s+(\w+)', content)
                    structure["backend"]["models"].extend(classes)

        # Services
        services_dir = BACKEND_DIR / "app" / "services"
        if services_dir.exists():
            for file in services_dir.glob("*.py"):
                if not file.name.startswith("_"):
                    structure["backend"]["services"].append(file.stem)

    # Scan frontend
    if FRONTEND_DIR.exists():
        # Pages
        pages_dir = FRONTEND_DIR / "pages"
        if pages_dir.exists():
            for file in pages_dir.rglob("*.tsx"):
                rel_path = file.relative_to(pages_dir)
                route = "/" + str(rel_path).replace(".tsx", "").replace("index", "").rstrip("/")
                structure["frontend"]["pages"].append(route or "/")

        # Components
        components_dir = FRONTEND_DIR / "components"
        if components_dir.exists():
            for file in components_dir.rglob("*.tsx"):
                structure["frontend"]["components"].append(file.stem)

    # Config files
    config_patterns = ["*.json", "*.yaml", "*.yml", "*.toml", "*.ini", ".env*"]
    for pattern in config_patterns:
        for file in PROJECT_ROOT.glob(pattern):
            if not any(x in str(file) for x in ["node_modules", ".git", "venv"]):
                structure["config_files"].append(file.name)

    # Existing docs
    for pattern in ["*.md", "docs/*.md"]:
        for file in PROJECT_ROOT.glob(pattern):
            structure["doc_files"].append(file.name)

    return structure


def read_key_files() -> dict:
    """Read content of key files for context."""

    key_files = {}

    files_to_read = [
        BACKEND_DIR / "app" / "main.py",
        BACKEND_DIR / "requirements.txt",
        FRONTEND_DIR / "package.json",
        PROJECT_ROOT / "README.md",
    ]

    for file_path in files_to_read:
        if file_path.exists():
            try:
                content = file_path.read_text()
                key_files[file_path.name] = content[:3000]  # First 3000 chars
            except:
                pass

    return key_files


def generate_documentation(structure: dict, key_files: dict) -> dict:
    """Generate documentation with Claude."""

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {"error": "ANTHROPIC_API_KEY not set"}

    print("Generating documentation...")

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=12000,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"""
Generate comprehensive documentation for ABVTrends based on this project structure.

## Project Structure
{json.dumps(structure, indent=2)}

## Key Files Content
{json.dumps(key_files, indent=2)}

## Project Description
ABVTrends is an AI-powered alcohol trend forecasting platform that:
- Tracks trending alcoholic beverages across multiple data sources
- Scores products using AI-driven trend analysis
- Provides forecasting for emerging trends
- Offers a web dashboard for exploration and analysis

Please generate:
1. README.md - Professional, complete with badges and setup instructions
2. ARCHITECTURE.md - System design with ASCII diagrams
3. API.md - Complete API reference
4. DEVELOPER_GUIDE.md - Onboarding and contribution guide
5. TESTING.md - Testing strategy and guidelines

Return as JSON with each document as a key.
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


def save_documentation(docs: dict, output_dir: Path = None):
    """Save generated documentation."""

    if output_dir is None:
        output_dir = PROJECT_ROOT / "docs"

    output_dir.mkdir(exist_ok=True)
    RESULTS_DIR.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    doc_mapping = {
        "readme": "README.md",
        "architecture": "ARCHITECTURE.md",
        "api": "API.md",
        "developer_guide": "DEVELOPER_GUIDE.md",
        "testing": "TESTING.md"
    }

    saved_files = []

    for key, filename in doc_mapping.items():
        content = docs.get(key)
        if content:
            # Save to docs directory
            doc_file = output_dir / filename
            with open(doc_file, "w") as f:
                f.write(content)
            saved_files.append(str(doc_file))
            print(f"Saved: {doc_file}")

            # Also save to results
            result_file = RESULTS_DIR / f"doc_{key}_{timestamp}.md"
            with open(result_file, "w") as f:
                f.write(content)

    # Save combined documentation
    combined_file = RESULTS_DIR / "docs_output.md"
    with open(combined_file, "w") as f:
        f.write("# ABVTrends Documentation\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")
        f.write("---\n\n")

        for key, filename in doc_mapping.items():
            content = docs.get(key)
            if content:
                f.write(f"# {filename}\n\n")
                f.write(content)
                f.write("\n\n---\n\n")

    print(f"\nCombined docs saved to: {combined_file}")

    # Handle raw response
    if "raw_response" in docs:
        raw_file = RESULTS_DIR / f"docs_raw_{timestamp}.md"
        with open(raw_file, "w") as f:
            f.write(docs["raw_response"])
        print(f"Raw response saved to: {raw_file}")

    return saved_files


def main():
    """Main execution flow."""

    print("=" * 60)
    print("CLAUDE-DOC-WRITER: AI Documentation Writer")
    print("=" * 60)

    # Parse arguments
    output_dir = None
    if len(sys.argv) > 1:
        output_dir = Path(sys.argv[1])

    # Scan project
    print("\nScanning project structure...")
    structure = scan_project_structure()

    print(f"  Backend routes: {len(structure['backend']['routes'])}")
    print(f"  Backend models: {len(structure['backend']['models'])}")
    print(f"  Frontend pages: {len(structure['frontend']['pages'])}")
    print(f"  Components: {len(structure['frontend']['components'])}")

    # Read key files
    key_files = read_key_files()
    print(f"  Key files read: {len(key_files)}")

    # Generate documentation
    docs = generate_documentation(structure, key_files)

    if "error" in docs:
        print(f"\nError: {docs['error']}")
        return 1

    # Save documentation
    saved_files = save_documentation(docs, output_dir)

    print("\n" + "=" * 60)
    print("DOCUMENTATION GENERATION COMPLETE")
    print("=" * 60)
    print(f"Generated {len(saved_files)} documentation files")

    return 0


if __name__ == "__main__":
    sys.exit(main())
