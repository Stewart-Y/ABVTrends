#!/usr/bin/env python3
"""
CLAUDE-INFRA-OPTIMIZER: AI Infrastructure Optimization Advisor

Analyzes infrastructure and recommends:
- AWS cost-savings opportunities
- Performance improvements
- EC2 vs Lambda decisions
- Database sharding strategies
- Redis/cache optimizations
- Scaling recommendations
- Resource right-sizing
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
You are CLAUDE-INFRA-OPTIMIZER, an expert in cloud infrastructure optimization.

You analyze infrastructure configurations and provide cost-saving and performance recommendations.

Analysis Areas:

1. **Compute Optimization**
   - EC2 instance right-sizing
   - EC2 vs Lambda decision matrix
   - Reserved vs On-Demand vs Spot instances
   - Auto-scaling configurations
   - Container orchestration (ECS/EKS)

2. **Database Optimization**
   - RDS instance sizing
   - Read replicas strategy
   - Connection pooling
   - Query performance
   - Sharding considerations
   - Aurora vs RDS vs DynamoDB

3. **Caching Strategy**
   - Redis/ElastiCache sizing
   - Cache hit rate optimization
   - TTL strategies
   - Cache warming approaches
   - Multi-tier caching

4. **Storage Optimization**
   - S3 storage classes
   - Lifecycle policies
   - CDN configuration
   - EBS volume optimization
   - Data archival strategies

5. **Network Optimization**
   - VPC architecture
   - NAT Gateway costs
   - Data transfer optimization
   - CloudFront configuration
   - API Gateway patterns

6. **Cost Analysis**
   - Current spend breakdown
   - Savings opportunities
   - Reserved capacity planning
   - Rightsizing recommendations
   - Unused resource identification

7. **Platform Comparisons**
   - AWS vs Railway vs Vercel
   - Serverless vs containers
   - Managed vs self-hosted
   - PaaS vs IaaS tradeoffs

ABVTrends Context:
- FastAPI backend (Python/async)
- PostgreSQL database
- Next.js frontend (Vercel-deployable)
- ML forecasting components
- Web scraping workloads
- API endpoints for trend data

Output Format (JSON):
{
  "summary": {
    "current_monthly_cost_estimate": "$X",
    "potential_savings": "$Y (Z%)",
    "optimization_priority": "high|medium|low",
    "risk_level": "low|medium|high"
  },
  "current_infrastructure": {
    "compute": "...",
    "database": "...",
    "cache": "...",
    "storage": "...",
    "hosting_platform": "..."
  },
  "compute_recommendations": [
    {
      "current": "...",
      "recommended": "...",
      "rationale": "...",
      "estimated_savings": "$X/month",
      "implementation": "..."
    }
  ],
  "database_recommendations": [
    {
      "area": "...",
      "current_state": "...",
      "recommendation": "...",
      "impact": "performance|cost|reliability",
      "implementation_steps": ["..."]
    }
  ],
  "caching_strategy": {
    "current": "...",
    "recommended": "...",
    "cache_layers": ["L1: in-memory", "L2: Redis", "..."],
    "ttl_recommendations": {},
    "estimated_hit_rate": "X%"
  },
  "storage_optimization": {
    "s3_recommendations": ["..."],
    "lifecycle_policies": ["..."],
    "cdn_strategy": "..."
  },
  "scaling_strategy": {
    "auto_scaling_config": {...},
    "peak_handling": "...",
    "cold_start_mitigation": "..."
  },
  "cost_breakdown": {
    "compute": "$X",
    "database": "$X",
    "storage": "$X",
    "network": "$X",
    "other": "$X"
  },
  "platform_recommendation": {
    "recommended_platform": "AWS|Railway|Vercel|hybrid",
    "rationale": "...",
    "migration_complexity": "low|medium|high"
  },
  "implementation_roadmap": [
    {
      "phase": 1,
      "name": "...",
      "changes": ["..."],
      "estimated_savings": "$X",
      "risk": "low|medium|high"
    }
  ],
  "monitoring_recommendations": [
    "..."
  ]
}
"""


def read_infrastructure_config() -> dict:
    """Read infrastructure configuration files."""

    config = {}

    # Docker compose files
    compose_files = list(PROJECT_ROOT.glob("**/docker-compose*.yml"))
    for f in compose_files[:3]:
        try:
            config[f.name] = f.read_text()
        except:
            pass

    # Dockerfile
    dockerfiles = list(PROJECT_ROOT.glob("**/Dockerfile*"))
    for f in dockerfiles[:3]:
        try:
            config[f.name] = f.read_text()
        except:
            pass

    # Vercel config
    vercel_config = PROJECT_ROOT / "vercel.json"
    if vercel_config.exists():
        try:
            config["vercel.json"] = vercel_config.read_text()
        except:
            pass

    # Railway config
    railway_config = PROJECT_ROOT / "railway.toml"
    if railway_config.exists():
        try:
            config["railway.toml"] = railway_config.read_text()
        except:
            pass

    # Package.json for frontend
    package_json = PROJECT_ROOT / "frontend" / "package.json"
    if package_json.exists():
        try:
            config["package.json"] = package_json.read_text()
        except:
            pass

    # Requirements.txt
    requirements = PROJECT_ROOT / "backend" / "requirements.txt"
    if requirements.exists():
        try:
            config["requirements.txt"] = requirements.read_text()
        except:
            pass

    # Environment example
    env_example = PROJECT_ROOT / ".env.example"
    if env_example.exists():
        try:
            config[".env.example"] = env_example.read_text()
        except:
            pass

    return config


def analyze_database_config() -> dict:
    """Analyze database configuration from code."""

    db_config = {
        "type": "Unknown",
        "async": False,
        "connection_pooling": False,
        "models": [],
        "migrations": False
    }

    # Check for database type
    requirements_file = BACKEND_DIR / "requirements.txt"
    if requirements_file.exists():
        try:
            content = requirements_file.read_text()
            if "psycopg" in content or "asyncpg" in content:
                db_config["type"] = "PostgreSQL"
            if "asyncpg" in content or "sqlalchemy[asyncio]" in content.lower():
                db_config["async"] = True
        except:
            pass

    # Check for connection pooling
    for file in BACKEND_DIR.rglob("*.py"):
        if "__pycache__" in str(file):
            continue
        try:
            content = file.read_text()
            if "pool_size" in content or "max_overflow" in content:
                db_config["connection_pooling"] = True
            if "create_async_engine" in content:
                db_config["async"] = True
        except:
            pass

    # Check for migrations
    alembic_dir = BACKEND_DIR / "alembic"
    if alembic_dir.exists():
        db_config["migrations"] = True
        migrations = list(alembic_dir.glob("versions/*.py"))
        db_config["migration_count"] = len(migrations)

    # Count models
    models_dir = BACKEND_DIR / "app" / "models"
    if models_dir.exists():
        for file in models_dir.glob("*.py"):
            try:
                content = file.read_text()
                classes = re.findall(r'class\s+(\w+)\s*\([^)]*Base[^)]*\):', content)
                db_config["models"].extend(classes)
            except:
                pass

    return db_config


def analyze_api_endpoints() -> dict:
    """Analyze API endpoints for performance considerations."""

    api_analysis = {
        "total_endpoints": 0,
        "async_endpoints": 0,
        "endpoints": []
    }

    api_dir = BACKEND_DIR / "app" / "api"
    if api_dir.exists():
        for file in api_dir.rglob("*.py"):
            if "__pycache__" in str(file):
                continue
            try:
                content = file.read_text()

                # Count endpoints
                patterns = [
                    (r'@\w+\.get\(["\']([^"\']+)["\']', "GET"),
                    (r'@\w+\.post\(["\']([^"\']+)["\']', "POST"),
                    (r'@\w+\.put\(["\']([^"\']+)["\']', "PUT"),
                    (r'@\w+\.delete\(["\']([^"\']+)["\']', "DELETE"),
                ]

                for pattern, method in patterns:
                    matches = re.findall(pattern, content)
                    for path in matches:
                        api_analysis["total_endpoints"] += 1
                        api_analysis["endpoints"].append({
                            "method": method,
                            "path": path,
                            "file": str(file.relative_to(PROJECT_ROOT))
                        })

                # Count async functions
                async_count = len(re.findall(r'async\s+def\s+\w+', content))
                api_analysis["async_endpoints"] += async_count

            except:
                pass

    return api_analysis


def analyze_caching() -> dict:
    """Analyze current caching implementation."""

    cache_analysis = {
        "redis_used": False,
        "in_memory_cache": False,
        "http_caching": False,
        "cache_patterns": []
    }

    # Check requirements
    requirements_file = BACKEND_DIR / "requirements.txt"
    if requirements_file.exists():
        try:
            content = requirements_file.read_text()
            if "redis" in content.lower():
                cache_analysis["redis_used"] = True
            if "cachetools" in content or "functools" in content:
                cache_analysis["in_memory_cache"] = True
        except:
            pass

    # Check code for caching patterns
    for file in BACKEND_DIR.rglob("*.py"):
        if "__pycache__" in str(file):
            continue
        try:
            content = file.read_text()

            if "@lru_cache" in content or "@cache" in content:
                cache_analysis["in_memory_cache"] = True
                cache_analysis["cache_patterns"].append("lru_cache decorator")

            if "redis" in content.lower() and ("set(" in content or "get(" in content):
                cache_analysis["redis_used"] = True
                cache_analysis["cache_patterns"].append("Redis key-value")

            if "Cache-Control" in content or "ETag" in content:
                cache_analysis["http_caching"] = True
                cache_analysis["cache_patterns"].append("HTTP caching headers")

        except:
            pass

    return cache_analysis


def analyze_static_assets() -> dict:
    """Analyze static assets and storage needs."""

    assets_analysis = {
        "frontend_assets": 0,
        "total_size_estimate": "0 MB",
        "image_count": 0,
        "cdn_configured": False
    }

    frontend_public = PROJECT_ROOT / "frontend" / "public"
    if frontend_public.exists():
        assets = list(frontend_public.rglob("*"))
        assets_analysis["frontend_assets"] = len([a for a in assets if a.is_file()])

        images = list(frontend_public.rglob("*.png")) + \
                 list(frontend_public.rglob("*.jpg")) + \
                 list(frontend_public.rglob("*.svg"))
        assets_analysis["image_count"] = len(images)

    # Check for CDN config
    next_config = PROJECT_ROOT / "frontend" / "next.config.js"
    if next_config.exists():
        try:
            content = next_config.read_text()
            if "images" in content and "domains" in content:
                assets_analysis["cdn_configured"] = True
        except:
            pass

    return assets_analysis


def optimize_infrastructure(
    infra_config: dict,
    db_config: dict,
    api_analysis: dict,
    cache_analysis: dict,
    assets_analysis: dict
) -> dict:
    """Generate infrastructure optimization recommendations with Claude."""

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {"error": "ANTHROPIC_API_KEY not set"}

    print("Analyzing infrastructure for optimization...")

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=10000,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"""
Analyze this infrastructure and provide optimization recommendations.

## Project: ABVTrends
An AI-powered alcohol trend forecasting platform.

## Tech Stack
- Backend: FastAPI (Python, async)
- Database: PostgreSQL
- Frontend: Next.js
- ML: Trend forecasting models
- Workloads: Web scraping, API serving, ML inference

## Infrastructure Configuration Files
{json.dumps(list(infra_config.keys()), indent=2)}

## Database Configuration
{json.dumps(db_config, indent=2)}

## API Analysis
- Total Endpoints: {api_analysis['total_endpoints']}
- Async Endpoints: {api_analysis['async_endpoints']}
- Sample endpoints: {json.dumps(api_analysis['endpoints'][:10], indent=2)}

## Caching Analysis
{json.dumps(cache_analysis, indent=2)}

## Static Assets
{json.dumps(assets_analysis, indent=2)}

## Key Infrastructure Files Content
{chr(10).join([f"### {k}{chr(10)}{v[:1500]}" for k, v in list(infra_config.items())[:5]])}

Please analyze and provide:
1. Current infrastructure assessment
2. Compute optimization (EC2 vs Lambda, sizing)
3. Database optimization (pooling, replicas, sharding)
4. Caching strategy recommendations
5. Storage and CDN optimization
6. Scaling strategy
7. Cost analysis and savings opportunities
8. Platform comparison (AWS vs Railway vs Vercel)
9. Implementation roadmap
10. Monitoring recommendations

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


def save_optimization_report(analysis: dict):
    """Save infrastructure optimization report."""

    RESULTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save JSON
    json_file = RESULTS_DIR / f"infra_optimization_{timestamp}.json"
    with open(json_file, "w") as f:
        json.dump(analysis, f, indent=2)

    # Save markdown report
    report_file = RESULTS_DIR / "infra_optimization.md"
    with open(report_file, "w") as f:
        f.write("# Infrastructure Optimization Report\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")

        if "summary" in analysis:
            summary = analysis["summary"]
            f.write("## Executive Summary\n\n")
            f.write(f"- **Current Monthly Cost:** {summary.get('current_monthly_cost_estimate', 'N/A')}\n")
            f.write(f"- **Potential Savings:** {summary.get('potential_savings', 'N/A')}\n")
            f.write(f"- **Optimization Priority:** {summary.get('optimization_priority', 'N/A')}\n")
            f.write(f"- **Risk Level:** {summary.get('risk_level', 'N/A')}\n\n")

        if "current_infrastructure" in analysis:
            infra = analysis["current_infrastructure"]
            f.write("## Current Infrastructure\n\n")
            for key, value in infra.items():
                f.write(f"- **{key.replace('_', ' ').title()}:** {value}\n")
            f.write("\n")

        if "compute_recommendations" in analysis:
            f.write("## Compute Recommendations\n\n")
            for rec in analysis["compute_recommendations"]:
                f.write(f"### {rec.get('recommended', 'Recommendation')}\n")
                f.write(f"**Current:** {rec.get('current', 'N/A')}\n\n")
                f.write(f"**Rationale:** {rec.get('rationale', 'N/A')}\n\n")
                f.write(f"**Estimated Savings:** {rec.get('estimated_savings', 'N/A')}\n\n")
                if rec.get("implementation"):
                    f.write(f"**Implementation:** {rec['implementation']}\n\n")

        if "database_recommendations" in analysis:
            f.write("## Database Recommendations\n\n")
            for rec in analysis["database_recommendations"]:
                f.write(f"### {rec.get('area', 'Area')}\n")
                f.write(f"**Current State:** {rec.get('current_state', 'N/A')}\n\n")
                f.write(f"**Recommendation:** {rec.get('recommendation', 'N/A')}\n\n")
                f.write(f"**Impact:** {rec.get('impact', 'N/A')}\n\n")
                if rec.get("implementation_steps"):
                    f.write("**Implementation Steps:**\n")
                    for step in rec["implementation_steps"]:
                        f.write(f"1. {step}\n")
                    f.write("\n")

        if "caching_strategy" in analysis:
            cache = analysis["caching_strategy"]
            f.write("## Caching Strategy\n\n")
            f.write(f"**Current:** {cache.get('current', 'N/A')}\n\n")
            f.write(f"**Recommended:** {cache.get('recommended', 'N/A')}\n\n")
            if cache.get("cache_layers"):
                f.write("**Cache Layers:**\n")
                for layer in cache["cache_layers"]:
                    f.write(f"- {layer}\n")
                f.write("\n")
            f.write(f"**Estimated Hit Rate:** {cache.get('estimated_hit_rate', 'N/A')}\n\n")

        if "scaling_strategy" in analysis:
            scaling = analysis["scaling_strategy"]
            f.write("## Scaling Strategy\n\n")
            f.write(f"**Peak Handling:** {scaling.get('peak_handling', 'N/A')}\n\n")
            f.write(f"**Cold Start Mitigation:** {scaling.get('cold_start_mitigation', 'N/A')}\n\n")
            if scaling.get("auto_scaling_config"):
                f.write("**Auto-scaling Configuration:**\n```json\n")
                f.write(json.dumps(scaling["auto_scaling_config"], indent=2))
                f.write("\n```\n\n")

        if "cost_breakdown" in analysis:
            costs = analysis["cost_breakdown"]
            f.write("## Cost Breakdown\n\n")
            f.write("| Category | Cost |\n")
            f.write("|----------|------|\n")
            for category, cost in costs.items():
                f.write(f"| {category.title()} | {cost} |\n")
            f.write("\n")

        if "platform_recommendation" in analysis:
            platform = analysis["platform_recommendation"]
            f.write("## Platform Recommendation\n\n")
            f.write(f"**Recommended Platform:** {platform.get('recommended_platform', 'N/A')}\n\n")
            f.write(f"**Rationale:** {platform.get('rationale', 'N/A')}\n\n")
            f.write(f"**Migration Complexity:** {platform.get('migration_complexity', 'N/A')}\n\n")

        if "implementation_roadmap" in analysis:
            f.write("## Implementation Roadmap\n\n")
            for phase in analysis["implementation_roadmap"]:
                f.write(f"### Phase {phase.get('phase', '?')}: {phase.get('name', 'Unknown')}\n")
                f.write(f"**Estimated Savings:** {phase.get('estimated_savings', 'N/A')}\n\n")
                f.write(f"**Risk:** {phase.get('risk', 'N/A')}\n\n")
                if phase.get("changes"):
                    f.write("**Changes:**\n")
                    for change in phase["changes"]:
                        f.write(f"- {change}\n")
                    f.write("\n")

        if "monitoring_recommendations" in analysis:
            f.write("## Monitoring Recommendations\n\n")
            for rec in analysis["monitoring_recommendations"]:
                f.write(f"- {rec}\n")
            f.write("\n")

        if "raw_response" in analysis:
            f.write("## Raw Analysis\n\n")
            f.write(analysis["raw_response"])

    print(f"Report saved to: {report_file}")
    return report_file


def main():
    """Main execution flow."""

    print("=" * 60)
    print("CLAUDE-INFRA-OPTIMIZER: AI Infrastructure Advisor")
    print("=" * 60)

    RESULTS_DIR.mkdir(exist_ok=True)

    # Gather infrastructure info
    print("\nReading infrastructure configuration...")
    infra_config = read_infrastructure_config()
    print(f"  Found {len(infra_config)} config files")

    print("Analyzing database configuration...")
    db_config = analyze_database_config()
    print(f"  Type: {db_config['type']}, Async: {db_config['async']}")

    print("Analyzing API endpoints...")
    api_analysis = analyze_api_endpoints()
    print(f"  Found {api_analysis['total_endpoints']} endpoints")

    print("Analyzing caching...")
    cache_analysis = analyze_caching()
    print(f"  Redis: {cache_analysis['redis_used']}, In-memory: {cache_analysis['in_memory_cache']}")

    print("Analyzing static assets...")
    assets_analysis = analyze_static_assets()
    print(f"  Found {assets_analysis['frontend_assets']} assets")

    # Generate recommendations
    analysis = optimize_infrastructure(
        infra_config, db_config, api_analysis, cache_analysis, assets_analysis
    )

    if "error" in analysis:
        print(f"\nError: {analysis['error']}")
        return 1

    # Save report
    report_file = save_optimization_report(analysis)

    # Print summary
    print("\n" + "=" * 60)
    print("INFRASTRUCTURE ANALYSIS COMPLETE")
    print("=" * 60)

    if "summary" in analysis:
        summary = analysis["summary"]
        print(f"Current Cost: {summary.get('current_monthly_cost_estimate', 'N/A')}")
        print(f"Potential Savings: {summary.get('potential_savings', 'N/A')}")
        print(f"Priority: {summary.get('optimization_priority', 'N/A')}")

    if "platform_recommendation" in analysis:
        platform = analysis["platform_recommendation"]
        print(f"\nRecommended Platform: {platform.get('recommended_platform', 'N/A')}")

    if "implementation_roadmap" in analysis:
        print(f"\nOptimization Phases: {len(analysis['implementation_roadmap'])}")
        for phase in analysis["implementation_roadmap"][:3]:
            print(f"  - Phase {phase.get('phase')}: {phase.get('name')} ({phase.get('estimated_savings', 'N/A')})")

    print(f"\nFull report: {report_file}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
