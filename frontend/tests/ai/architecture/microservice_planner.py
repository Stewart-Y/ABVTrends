#!/usr/bin/env python3
"""
CLAUDE-MICROSERVICE-ARCHITECT: AI Microservice Planner

Analyzes monolith codebase and recommends:
- Microservice boundaries
- Service-to-service API contracts
- Data ownership rules
- Async communication plans
- Deployment strategies
- Migration roadmap
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
You are CLAUDE-MICROSERVICE-ARCHITECT, an expert in distributed systems and microservice architecture.

You analyze monolithic applications and recommend microservice decomposition strategies.

Analysis Areas:

1. **Domain Analysis**
   - Identify bounded contexts
   - Map domain entities
   - Define aggregates
   - Identify domain events

2. **Service Boundaries**
   - Recommend service split points
   - Define service responsibilities
   - Identify shared vs owned data
   - Map service dependencies

3. **API Contracts**
   - REST API specifications
   - gRPC service definitions
   - Event schemas
   - API versioning strategy

4. **Data Architecture**
   - Database per service
   - Shared data patterns
   - Event sourcing opportunities
   - CQRS patterns

5. **Communication Patterns**
   - Sync vs async
   - Message queues (RabbitMQ, Kafka)
   - Event-driven architecture
   - Saga patterns for transactions

6. **Migration Strategy**
   - Strangler fig pattern
   - Phase-by-phase migration
   - Database decomposition
   - Traffic routing

ABVTrends Context:
- Alcohol trend forecasting platform
- Key domains: Products, Trends, Signals, Forecasts, Scraping
- FastAPI backend, PostgreSQL database
- ML forecasting engine

Output Format (JSON):
{
  "summary": {
    "current_state": "monolith description",
    "recommended_services": 5,
    "migration_complexity": "low|medium|high",
    "estimated_phases": 3
  },
  "domains": [
    {
      "name": "Domain Name",
      "bounded_context": "...",
      "entities": ["..."],
      "aggregates": ["..."],
      "events": ["..."]
    }
  ],
  "services": [
    {
      "name": "service-name",
      "responsibility": "...",
      "domain": "...",
      "api_endpoints": [
        {"method": "GET", "path": "/...", "description": "..."}
      ],
      "owns_data": ["table1", "table2"],
      "depends_on": ["other-service"],
      "events_published": ["..."],
      "events_consumed": ["..."]
    }
  ],
  "data_strategy": {
    "pattern": "database-per-service|shared-database|...",
    "migration_approach": "...",
    "consistency_model": "eventual|strong"
  },
  "communication": {
    "sync": ["service pairs"],
    "async": ["event flows"],
    "queue_technology": "RabbitMQ|Kafka|SQS"
  },
  "migration_phases": [
    {
      "phase": 1,
      "name": "...",
      "services_extracted": ["..."],
      "duration_estimate": "2-4 weeks",
      "risks": ["..."],
      "rollback_plan": "..."
    }
  ],
  "infrastructure": {
    "container_strategy": "Docker + Kubernetes",
    "service_mesh": "Istio|Linkerd|None",
    "api_gateway": "Kong|AWS API Gateway",
    "monitoring": "Prometheus + Grafana"
  }
}
"""


def scan_backend_code() -> dict:
    """Scan backend code for analysis."""

    code_files = {}

    for file in BACKEND_DIR.rglob("*.py"):
        if any(x in str(file) for x in ["__pycache__", "venv", ".git"]):
            continue

        try:
            content = file.read_text()
            relative_path = file.relative_to(PROJECT_ROOT)
            code_files[str(relative_path)] = content
        except:
            pass

    return code_files


def extract_models(code_files: dict) -> list:
    """Extract SQLAlchemy model definitions."""

    models = []

    for path, content in code_files.items():
        if "models" in path:
            # Find class definitions
            classes = re.findall(r'class\s+(\w+)\s*\([^)]*Base[^)]*\):', content)
            for class_name in classes:
                # Find columns
                columns = re.findall(r'(\w+)\s*=\s*Column\((\w+)', content)
                # Find relationships
                relationships = re.findall(r'(\w+)\s*=\s*relationship\(["\'](\w+)["\']', content)

                models.append({
                    "name": class_name,
                    "file": path,
                    "columns": [{"name": c[0], "type": c[1]} for c in columns[:10]],
                    "relationships": [{"name": r[0], "target": r[1]} for r in relationships]
                })

    return models


def extract_routes(code_files: dict) -> list:
    """Extract API route definitions."""

    routes = []

    for path, content in code_files.items():
        if "api" in path:
            # Find route decorators
            patterns = [
                (r'@\w+\.get\(["\']([^"\']+)["\']', "GET"),
                (r'@\w+\.post\(["\']([^"\']+)["\']', "POST"),
                (r'@\w+\.put\(["\']([^"\']+)["\']', "PUT"),
                (r'@\w+\.delete\(["\']([^"\']+)["\']', "DELETE"),
            ]

            for pattern, method in patterns:
                matches = re.findall(pattern, content)
                for route_path in matches:
                    routes.append({
                        "method": method,
                        "path": route_path,
                        "file": path
                    })

    return routes


def extract_services(code_files: dict) -> list:
    """Extract service layer definitions."""

    services = []

    for path, content in code_files.items():
        if "services" in path:
            # Find class definitions
            classes = re.findall(r'class\s+(\w+)(?:\([^)]*\))?:', content)
            # Find async functions
            functions = re.findall(r'async\s+def\s+(\w+)\s*\(', content)

            if classes or functions:
                services.append({
                    "file": path,
                    "classes": classes,
                    "functions": functions[:20]
                })

    return services


def plan_microservices(code_files: dict, models: list, routes: list, services: list) -> dict:
    """Plan microservice architecture with Claude."""

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {"error": "ANTHROPIC_API_KEY not set"}

    print("Analyzing codebase for microservice opportunities...")

    # Build code summary
    code_summary = ""
    for path, content in list(code_files.items())[:15]:
        code_summary += f"\n### {path}\n```python\n{content[:2000]}\n```\n"

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=12000,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"""
Analyze this monolithic backend and recommend a microservice architecture.

## Project: ABVTrends
An AI-powered alcohol trend forecasting platform.

## Database Models ({len(models)} models)
{json.dumps(models, indent=2)}

## API Routes ({len(routes)} routes)
{json.dumps(routes, indent=2)}

## Service Layer ({len(services)} services)
{json.dumps(services, indent=2)}

## Code Files (sample)
{code_summary[:20000]}

Please analyze and provide:
1. Domain-driven design analysis
2. Recommended microservice boundaries
3. Service-to-service API contracts
4. Data ownership and migration strategy
5. Communication patterns (sync/async)
6. Phase-by-phase migration plan
7. Infrastructure recommendations

Return as JSON.
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


def save_plan(plan: dict):
    """Save microservice plan."""

    RESULTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save JSON
    json_file = RESULTS_DIR / f"microservice_plan_{timestamp}.json"
    with open(json_file, "w") as f:
        json.dump(plan, f, indent=2)

    # Save markdown report
    report_file = RESULTS_DIR / "microservice_plan.md"
    with open(report_file, "w") as f:
        f.write("# Microservice Architecture Plan\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")

        if "summary" in plan:
            summary = plan["summary"]
            f.write("## Executive Summary\n\n")
            f.write(f"- **Current State:** {summary.get('current_state', 'N/A')}\n")
            f.write(f"- **Recommended Services:** {summary.get('recommended_services', 'N/A')}\n")
            f.write(f"- **Migration Complexity:** {summary.get('migration_complexity', 'N/A')}\n")
            f.write(f"- **Estimated Phases:** {summary.get('estimated_phases', 'N/A')}\n\n")

        if "domains" in plan:
            f.write("## Domain Analysis\n\n")
            for domain in plan["domains"]:
                f.write(f"### {domain.get('name', 'Unknown')}\n")
                f.write(f"**Bounded Context:** {domain.get('bounded_context', 'N/A')}\n\n")
                f.write(f"**Entities:** {', '.join(domain.get('entities', []))}\n\n")
                f.write(f"**Events:** {', '.join(domain.get('events', []))}\n\n")

        if "services" in plan:
            f.write("## Recommended Services\n\n")
            for service in plan["services"]:
                f.write(f"### {service.get('name', 'Unknown')}\n")
                f.write(f"**Responsibility:** {service.get('responsibility', 'N/A')}\n\n")
                f.write(f"**Domain:** {service.get('domain', 'N/A')}\n\n")

                if service.get("api_endpoints"):
                    f.write("**API Endpoints:**\n")
                    for ep in service["api_endpoints"][:5]:
                        f.write(f"- `{ep.get('method', '')} {ep.get('path', '')}`\n")
                    f.write("\n")

                if service.get("owns_data"):
                    f.write(f"**Owns Data:** {', '.join(service['owns_data'])}\n\n")

                if service.get("depends_on"):
                    f.write(f"**Depends On:** {', '.join(service['depends_on'])}\n\n")

        if "migration_phases" in plan:
            f.write("## Migration Roadmap\n\n")
            for phase in plan["migration_phases"]:
                f.write(f"### Phase {phase.get('phase', '?')}: {phase.get('name', 'Unknown')}\n")
                f.write(f"**Duration:** {phase.get('duration_estimate', 'N/A')}\n\n")
                f.write(f"**Services Extracted:** {', '.join(phase.get('services_extracted', []))}\n\n")

                if phase.get("risks"):
                    f.write("**Risks:**\n")
                    for risk in phase["risks"]:
                        f.write(f"- {risk}\n")
                    f.write("\n")

        if "infrastructure" in plan:
            infra = plan["infrastructure"]
            f.write("## Infrastructure Recommendations\n\n")
            f.write(f"- **Container Strategy:** {infra.get('container_strategy', 'N/A')}\n")
            f.write(f"- **Service Mesh:** {infra.get('service_mesh', 'N/A')}\n")
            f.write(f"- **API Gateway:** {infra.get('api_gateway', 'N/A')}\n")
            f.write(f"- **Monitoring:** {infra.get('monitoring', 'N/A')}\n\n")

        if "raw_response" in plan:
            f.write("## Raw Analysis\n\n")
            f.write(plan["raw_response"])

    print(f"Plan saved to: {report_file}")
    return report_file


def main():
    """Main execution flow."""

    print("=" * 60)
    print("CLAUDE-MICROSERVICE-ARCHITECT: Microservice Planner")
    print("=" * 60)

    RESULTS_DIR.mkdir(exist_ok=True)

    # Scan codebase
    print("\nScanning backend codebase...")
    code_files = scan_backend_code()
    print(f"  Found {len(code_files)} Python files")

    print("Extracting models...")
    models = extract_models(code_files)
    print(f"  Found {len(models)} models")

    print("Extracting routes...")
    routes = extract_routes(code_files)
    print(f"  Found {len(routes)} routes")

    print("Extracting services...")
    services = extract_services(code_files)
    print(f"  Found {len(services)} service files")

    # Plan microservices
    plan = plan_microservices(code_files, models, routes, services)

    if "error" in plan:
        print(f"\nError: {plan['error']}")
        return 1

    # Save plan
    report_file = save_plan(plan)

    # Print summary
    print("\n" + "=" * 60)
    print("MICROSERVICE PLANNING COMPLETE")
    print("=" * 60)

    if "summary" in plan:
        summary = plan["summary"]
        print(f"Recommended Services: {summary.get('recommended_services', 'N/A')}")
        print(f"Migration Complexity: {summary.get('migration_complexity', 'N/A')}")
        print(f"Estimated Phases: {summary.get('estimated_phases', 'N/A')}")

    if "services" in plan:
        print(f"\nServices identified: {len(plan['services'])}")
        for svc in plan["services"][:5]:
            print(f"  - {svc.get('name', 'Unknown')}")

    print(f"\nFull plan: {report_file}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
