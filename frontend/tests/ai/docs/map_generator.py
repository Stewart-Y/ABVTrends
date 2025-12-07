#!/usr/bin/env python3
"""
CLAUDE-CODE-MAP: AI Glossary + Codebase Map Generator

Generates:
- Full code glossary
- Component dependency graph
- Service map
- Module relationships
- Database schema visualization
"""

import os
import sys
import re
import json
from datetime import datetime
from pathlib import Path
from collections import defaultdict

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
You are CLAUDE-CODE-MAP, an expert software architect and documentation specialist.

You generate:
1. Codebase Glossary - Definitions of key terms, classes, functions
2. Module Dependency Map - How modules depend on each other
3. Service Interaction Diagram - How services communicate
4. Database Relationship Diagram - Entity relationships (ASCII)
5. Component Hierarchy - Frontend component structure
6. API Flow Diagram - Request/response flows

Output Format:
Use ASCII art for diagrams. Make them clear and readable.

Example dependency diagram:
```
┌─────────────┐     ┌─────────────┐
│   Service   │────>│  Repository │
│   Layer     │     │   Layer     │
└─────────────┘     └─────────────┘
       │                   │
       v                   v
┌─────────────┐     ┌─────────────┐
│    API      │     │  Database   │
│   Routes    │     │   Models    │
└─────────────┘     └─────────────┘
```

Sections to include:
1. Overview
2. Glossary (alphabetical)
3. Backend Architecture
4. Frontend Architecture
5. Database Schema
6. API Map
7. Key Workflows
8. Dependencies Graph

Return as structured markdown.
"""


def scan_python_modules(directory: Path) -> dict:
    """Scan Python files and extract module information."""

    modules = {}

    for file in directory.rglob("*.py"):
        if any(x in str(file) for x in ["venv", "__pycache__", ".git"]):
            continue

        try:
            content = file.read_text()
            relative_path = file.relative_to(PROJECT_ROOT)

            # Extract classes
            classes = re.findall(r'class\s+(\w+)(?:\([^)]*\))?:', content)

            # Extract functions
            functions = re.findall(r'def\s+(\w+)\s*\(', content)

            # Extract imports
            imports = re.findall(r'^(?:from\s+(\S+)\s+)?import\s+(.+)$', content, re.MULTILINE)

            # Extract docstrings
            module_doc = re.search(r'^"""(.*?)"""', content, re.DOTALL)

            modules[str(relative_path)] = {
                "classes": classes,
                "functions": [f for f in functions if not f.startswith("_")],
                "imports": imports,
                "docstring": module_doc.group(1)[:200] if module_doc else None
            }

        except Exception as e:
            continue

    return modules


def scan_typescript_components(directory: Path) -> dict:
    """Scan TypeScript files and extract component information."""

    components = {}

    for file in directory.rglob("*.tsx"):
        if "node_modules" in str(file):
            continue

        try:
            content = file.read_text()
            relative_path = file.relative_to(PROJECT_ROOT)

            # Extract component names
            component_matches = re.findall(
                r'(?:export\s+(?:default\s+)?)?(?:function|const)\s+(\w+)',
                content
            )

            # Extract imports
            imports = re.findall(r"import\s+.*?from\s+['\"]([^'\"]+)['\"]", content)

            # Extract hooks used
            hooks = re.findall(r'use[A-Z]\w+', content)

            components[str(relative_path)] = {
                "components": [c for c in component_matches if c[0].isupper()],
                "imports": imports,
                "hooks": list(set(hooks))
            }

        except:
            continue

    return components


def build_dependency_graph(modules: dict) -> dict:
    """Build a dependency graph from imports."""

    graph = defaultdict(list)

    for module_path, info in modules.items():
        for from_module, imported in info.get("imports", []):
            if from_module and "app" in from_module:
                graph[module_path].append(from_module)

    return dict(graph)


def extract_api_routes(directory: Path) -> list:
    """Extract API route definitions."""

    routes = []
    api_dir = directory / "app" / "api" / "v1"

    if api_dir.exists():
        for file in api_dir.glob("*.py"):
            try:
                content = file.read_text()

                # Extract routes with their handlers
                patterns = [
                    (r'@\w+\.(get)\(["\']([^"\']+)["\']', "GET"),
                    (r'@\w+\.(post)\(["\']([^"\']+)["\']', "POST"),
                    (r'@\w+\.(put)\(["\']([^"\']+)["\']', "PUT"),
                    (r'@\w+\.(delete)\(["\']([^"\']+)["\']', "DELETE"),
                ]

                for pattern, method in patterns:
                    matches = re.findall(pattern, content)
                    for _, path in matches:
                        routes.append({
                            "method": method,
                            "path": path,
                            "file": file.name
                        })

            except:
                continue

    return routes


def extract_models(directory: Path) -> list:
    """Extract SQLAlchemy model definitions."""

    models = []
    models_dir = directory / "app" / "models"

    if models_dir.exists():
        for file in models_dir.glob("*.py"):
            try:
                content = file.read_text()

                # Extract model classes
                class_matches = re.findall(
                    r'class\s+(\w+)\(.*?Base.*?\):',
                    content
                )

                for class_name in class_matches:
                    # Extract columns
                    columns = re.findall(
                        r'(\w+)\s*=\s*Column\((\w+)',
                        content
                    )

                    # Extract relationships
                    relationships = re.findall(
                        r'(\w+)\s*=\s*relationship\(["\'](\w+)["\']',
                        content
                    )

                    models.append({
                        "name": class_name,
                        "file": file.name,
                        "columns": columns,
                        "relationships": relationships
                    })

            except:
                continue

    return models


def generate_code_map(modules: dict, components: dict, routes: list, models: list, dep_graph: dict) -> str:
    """Generate comprehensive code map with Claude."""

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return "Error: ANTHROPIC_API_KEY not set"

    print("Generating codebase map with Claude...")

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=12000,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"""
Generate a comprehensive codebase map for ABVTrends.

## Backend Python Modules
{json.dumps(modules, indent=2, default=str)[:8000]}

## Frontend Components
{json.dumps(components, indent=2)[:4000]}

## API Routes
{json.dumps(routes, indent=2)}

## Database Models
{json.dumps(models, indent=2)}

## Module Dependencies
{json.dumps(dep_graph, indent=2)}

## Project Context
ABVTrends is an AI-powered alcohol trend forecasting platform:
- Backend: FastAPI, SQLAlchemy, PostgreSQL
- Frontend: Next.js, React, TypeScript
- Features: Trend scoring, forecasting, web scraping

Please generate:
1. Overview section
2. Comprehensive glossary
3. Backend architecture diagram (ASCII)
4. Frontend component hierarchy
5. Database ER diagram (ASCII)
6. API route map
7. Key workflows/data flows
8. Module dependency graph

Use clear ASCII diagrams and markdown formatting.
"""
                }
            ]
        )

        return response.content[0].text

    except Exception as e:
        return f"Error: {e}"


def save_code_map(code_map: str):
    """Save the code map to files."""

    RESULTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save main code map
    map_file = RESULTS_DIR / "code_map.md"
    with open(map_file, "w") as f:
        f.write("# ABVTrends Codebase Map\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")
        f.write("---\n\n")
        f.write(code_map)

    print(f"\nCode map saved to: {map_file}")

    # Also save timestamped version
    versioned_file = RESULTS_DIR / f"code_map_{timestamp}.md"
    with open(versioned_file, "w") as f:
        f.write("# ABVTrends Codebase Map\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")
        f.write("---\n\n")
        f.write(code_map)

    # Save to project docs
    docs_dir = PROJECT_ROOT / "docs"
    docs_dir.mkdir(exist_ok=True)
    docs_file = docs_dir / "CODE_MAP.md"
    with open(docs_file, "w") as f:
        f.write("# ABVTrends Codebase Map\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")
        f.write("---\n\n")
        f.write(code_map)

    print(f"Also saved to: {docs_file}")


def main():
    """Main execution flow."""

    print("=" * 60)
    print("CLAUDE-CODE-MAP: Codebase Map Generator")
    print("=" * 60)

    # Scan codebase
    print("\nScanning codebase...")

    print("  Scanning Python modules...")
    modules = scan_python_modules(BACKEND_DIR)
    print(f"    Found {len(modules)} Python modules")

    print("  Scanning TypeScript components...")
    components = scan_typescript_components(FRONTEND_DIR)
    print(f"    Found {len(components)} TypeScript files")

    print("  Extracting API routes...")
    routes = extract_api_routes(BACKEND_DIR)
    print(f"    Found {len(routes)} API routes")

    print("  Extracting database models...")
    models = extract_models(BACKEND_DIR)
    print(f"    Found {len(models)} models")

    print("  Building dependency graph...")
    dep_graph = build_dependency_graph(modules)
    print(f"    Found {len(dep_graph)} module dependencies")

    # Generate code map
    code_map = generate_code_map(modules, components, routes, models, dep_graph)

    if code_map.startswith("Error:"):
        print(f"\n{code_map}")
        return 1

    # Save results
    save_code_map(code_map)

    print("\n" + "=" * 60)
    print("CODE MAP GENERATION COMPLETE")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
