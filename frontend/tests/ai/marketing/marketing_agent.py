#!/usr/bin/env python3
"""
CLAUDE-MARKETING: AI Marketing Content Generator

Generates marketing content for ABVTrends:
- SEO-optimized landing pages
- Social media campaigns
- Email marketing funnels
- Ad copy (Google, Meta)
- Content calendar
- Growth strategies
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
You are CLAUDE-MARKETING, an expert digital marketing strategist specializing in B2B SaaS and data platforms.

You create comprehensive marketing strategies and content for tech products.

Marketing Areas:

1. **SEO Strategy**
   - Keyword research
   - On-page optimization
   - Content strategy
   - Technical SEO
   - Link building opportunities
   - Local SEO (if applicable)

2. **Content Marketing**
   - Blog post topics
   - Thought leadership pieces
   - Case studies
   - Whitepapers
   - Infographics
   - Video content ideas

3. **Social Media**
   - Platform strategies (LinkedIn, Twitter, Instagram)
   - Content calendar
   - Engagement tactics
   - Influencer partnerships
   - Community building

4. **Email Marketing**
   - Welcome sequences
   - Nurture campaigns
   - Product updates
   - Re-engagement flows
   - A/B testing strategies

5. **Paid Advertising**
   - Google Ads strategy
   - Meta (Facebook/Instagram) ads
   - LinkedIn ads for B2B
   - Retargeting campaigns
   - Budget allocation

6. **Growth Hacking**
   - Viral loops
   - Referral programs
   - Partnership opportunities
   - Product-led growth tactics
   - Community-led growth

ABVTrends Context:
- AI-powered alcohol trend forecasting platform
- Target audience: Beverage distributors, bars, restaurants, retailers
- Key features: Trend predictions, signal analysis, product discovery
- Value proposition: Data-driven buying decisions for alcohol products
- Competition: Manual trend tracking, basic analytics tools

Output Format (JSON):
{
  "summary": {
    "primary_channels": ["..."],
    "estimated_monthly_budget": "$X",
    "key_messages": ["..."],
    "target_audience_segments": ["..."]
  },
  "brand_positioning": {
    "tagline": "...",
    "value_propositions": ["..."],
    "differentiators": ["..."],
    "brand_voice": "..."
  },
  "seo_strategy": {
    "primary_keywords": [
      {"keyword": "...", "search_volume": "X/mo", "difficulty": "low|medium|high", "intent": "informational|transactional"}
    ],
    "long_tail_keywords": ["..."],
    "content_clusters": [
      {"pillar": "...", "cluster_topics": ["..."]}
    ],
    "technical_recommendations": ["..."]
  },
  "content_calendar": {
    "blog_posts": [
      {"title": "...", "keywords": ["..."], "publish_week": 1, "content_type": "how-to|listicle|case-study"}
    ],
    "social_posts": [
      {"platform": "linkedin|twitter", "content": "...", "hashtags": ["..."], "best_time": "..."}
    ]
  },
  "email_campaigns": {
    "welcome_sequence": [
      {"day": 0, "subject": "...", "purpose": "...", "cta": "..."}
    ],
    "nurture_sequence": [
      {"trigger": "...", "subject": "...", "content_focus": "..."}
    ]
  },
  "paid_advertising": {
    "google_ads": {
      "campaigns": [
        {"name": "...", "type": "search|display", "keywords": ["..."], "budget": "$X/day"}
      ],
      "ad_copy": [
        {"headline": "...", "description": "...", "cta": "..."}
      ]
    },
    "meta_ads": {
      "audiences": ["..."],
      "ad_creative_ideas": ["..."],
      "budget_allocation": "..."
    }
  },
  "growth_tactics": {
    "quick_wins": ["..."],
    "medium_term": ["..."],
    "long_term": ["..."],
    "viral_mechanics": ["..."]
  },
  "metrics_to_track": {
    "awareness": ["..."],
    "acquisition": ["..."],
    "activation": ["..."],
    "retention": ["..."],
    "revenue": ["..."]
  },
  "competitive_positioning": {
    "competitors": ["..."],
    "our_advantages": ["..."],
    "messaging_against_competitors": "..."
  }
}
"""


def read_product_info() -> dict:
    """Read product information from project files."""

    product_info = {
        "name": "ABVTrends",
        "description": "",
        "features": [],
        "tech_stack": []
    }

    # Read README
    readme_file = PROJECT_ROOT / "README.md"
    if readme_file.exists():
        try:
            product_info["readme"] = readme_file.read_text()[:5000]
        except:
            pass

    # Read documentation
    doc_file = PROJECT_ROOT / "DOCUMENTATION.md"
    if doc_file.exists():
        try:
            product_info["documentation"] = doc_file.read_text()[:5000]
        except:
            pass

    # Read frontend pages for feature understanding
    pages_dir = PROJECT_ROOT / "frontend" / "pages"
    if pages_dir.exists():
        for file in pages_dir.glob("*.tsx"):
            product_info["features"].append(file.stem)

    # Read API endpoints
    api_dir = PROJECT_ROOT / "backend" / "app" / "api"
    if api_dir.exists():
        for file in api_dir.rglob("*.py"):
            if "__pycache__" not in str(file):
                try:
                    content = file.read_text()
                    # Extract route descriptions from docstrings
                    docstrings = re.findall(r'"""([^"]+)"""', content)
                    product_info["features"].extend([d.strip()[:100] for d in docstrings[:5]])
                except:
                    pass

    return product_info


def read_existing_content() -> dict:
    """Read any existing marketing or content files."""

    content = {}

    # Look for marketing-related files
    marketing_files = [
        PROJECT_ROOT / "docs" / "marketing",
        PROJECT_ROOT / "marketing",
        PROJECT_ROOT / "content"
    ]

    for dir_path in marketing_files:
        if dir_path.exists():
            for file in dir_path.rglob("*"):
                if file.is_file() and file.suffix in [".md", ".txt", ".json"]:
                    try:
                        content[file.name] = file.read_text()[:2000]
                    except:
                        pass

    return content


def read_competitor_info() -> list:
    """Identify potential competitors from market context."""

    # These would typically come from market research
    # For ABVTrends, these are alcohol industry data competitors
    competitors = [
        {
            "name": "Nielsen",
            "description": "Traditional market research for alcohol industry",
            "strengths": ["Established brand", "Large dataset", "Industry standard"],
            "weaknesses": ["Expensive", "Slow updates", "Not AI-powered"]
        },
        {
            "name": "IWSR",
            "description": "Drinks market analysis",
            "strengths": ["Global coverage", "Industry reports"],
            "weaknesses": ["Manual analysis", "Delayed insights"]
        },
        {
            "name": "BevAlc Insights",
            "description": "Beverage alcohol analytics",
            "strengths": ["Industry focused"],
            "weaknesses": ["Limited AI", "Basic forecasting"]
        }
    ]

    return competitors


def generate_marketing_strategy(product_info: dict, existing_content: dict, competitors: list) -> dict:
    """Generate comprehensive marketing strategy with Claude."""

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {"error": "ANTHROPIC_API_KEY not set"}

    print("Generating marketing strategy...")

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=12000,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"""
Create a comprehensive marketing strategy for ABVTrends.

## Product Overview
**Name:** ABVTrends
**Type:** AI-powered alcohol trend forecasting platform

## Product Features
{json.dumps(product_info.get('features', []), indent=2)}

## Product Documentation
{product_info.get('readme', 'N/A')[:3000]}

## Target Market
- Primary: Beverage distributors, wholesalers
- Secondary: Bars, restaurants, retailers
- Tertiary: Beverage brands, marketing agencies

## Key Value Propositions
1. AI-powered trend predictions (not just historical data)
2. Real-time signal analysis from multiple sources
3. Product discovery for emerging trends
4. Actionable insights for buying decisions

## Competitive Landscape
{json.dumps(competitors, indent=2)}

## Existing Content
{json.dumps(list(existing_content.keys()), indent=2)}

Please create a comprehensive marketing strategy including:
1. Brand positioning and messaging
2. SEO strategy with keywords
3. Content calendar (4 weeks)
4. Email marketing sequences
5. Paid advertising strategy
6. Growth tactics
7. Success metrics

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


def save_marketing_output(strategy: dict):
    """Save marketing strategy and content."""

    RESULTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save JSON
    json_file = RESULTS_DIR / f"marketing_strategy_{timestamp}.json"
    with open(json_file, "w") as f:
        json.dump(strategy, f, indent=2)

    # Save markdown report
    report_file = RESULTS_DIR / "marketing_output.md"
    with open(report_file, "w") as f:
        f.write("# ABVTrends Marketing Strategy\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")

        if "summary" in strategy:
            summary = strategy["summary"]
            f.write("## Executive Summary\n\n")
            f.write(f"**Primary Channels:** {', '.join(summary.get('primary_channels', []))}\n\n")
            f.write(f"**Monthly Budget:** {summary.get('estimated_monthly_budget', 'N/A')}\n\n")
            if summary.get("key_messages"):
                f.write("**Key Messages:**\n")
                for msg in summary["key_messages"]:
                    f.write(f"- {msg}\n")
                f.write("\n")
            if summary.get("target_audience_segments"):
                f.write("**Target Segments:**\n")
                for seg in summary["target_audience_segments"]:
                    f.write(f"- {seg}\n")
                f.write("\n")

        if "brand_positioning" in strategy:
            brand = strategy["brand_positioning"]
            f.write("## Brand Positioning\n\n")
            f.write(f"**Tagline:** *{brand.get('tagline', 'N/A')}*\n\n")
            f.write(f"**Brand Voice:** {brand.get('brand_voice', 'N/A')}\n\n")
            if brand.get("value_propositions"):
                f.write("**Value Propositions:**\n")
                for vp in brand["value_propositions"]:
                    f.write(f"- {vp}\n")
                f.write("\n")
            if brand.get("differentiators"):
                f.write("**Key Differentiators:**\n")
                for diff in brand["differentiators"]:
                    f.write(f"- {diff}\n")
                f.write("\n")

        if "seo_strategy" in strategy:
            seo = strategy["seo_strategy"]
            f.write("## SEO Strategy\n\n")

            if seo.get("primary_keywords"):
                f.write("### Primary Keywords\n\n")
                f.write("| Keyword | Volume | Difficulty | Intent |\n")
                f.write("|---------|--------|------------|--------|\n")
                for kw in seo["primary_keywords"][:10]:
                    f.write(f"| {kw.get('keyword', 'N/A')} | {kw.get('search_volume', 'N/A')} | {kw.get('difficulty', 'N/A')} | {kw.get('intent', 'N/A')} |\n")
                f.write("\n")

            if seo.get("content_clusters"):
                f.write("### Content Clusters\n\n")
                for cluster in seo["content_clusters"]:
                    f.write(f"**Pillar:** {cluster.get('pillar', 'N/A')}\n")
                    if cluster.get("cluster_topics"):
                        for topic in cluster["cluster_topics"]:
                            f.write(f"  - {topic}\n")
                    f.write("\n")

        if "content_calendar" in strategy:
            calendar = strategy["content_calendar"]
            f.write("## Content Calendar\n\n")

            if calendar.get("blog_posts"):
                f.write("### Blog Posts\n\n")
                f.write("| Week | Title | Type | Keywords |\n")
                f.write("|------|-------|------|----------|\n")
                for post in calendar["blog_posts"]:
                    keywords = ", ".join(post.get("keywords", [])[:3])
                    f.write(f"| {post.get('publish_week', 'N/A')} | {post.get('title', 'N/A')} | {post.get('content_type', 'N/A')} | {keywords} |\n")
                f.write("\n")

            if calendar.get("social_posts"):
                f.write("### Social Media Posts\n\n")
                for post in calendar["social_posts"][:10]:
                    f.write(f"**{post.get('platform', 'N/A').title()}** ({post.get('best_time', 'N/A')})\n")
                    f.write(f"> {post.get('content', 'N/A')}\n")
                    if post.get("hashtags"):
                        f.write(f"Hashtags: {' '.join(post['hashtags'])}\n")
                    f.write("\n")

        if "email_campaigns" in strategy:
            email = strategy["email_campaigns"]
            f.write("## Email Campaigns\n\n")

            if email.get("welcome_sequence"):
                f.write("### Welcome Sequence\n\n")
                for em in email["welcome_sequence"]:
                    f.write(f"**Day {em.get('day', 'N/A')}:** {em.get('subject', 'N/A')}\n")
                    f.write(f"- Purpose: {em.get('purpose', 'N/A')}\n")
                    f.write(f"- CTA: {em.get('cta', 'N/A')}\n\n")

            if email.get("nurture_sequence"):
                f.write("### Nurture Sequence\n\n")
                for em in email["nurture_sequence"]:
                    f.write(f"**Trigger:** {em.get('trigger', 'N/A')}\n")
                    f.write(f"- Subject: {em.get('subject', 'N/A')}\n")
                    f.write(f"- Focus: {em.get('content_focus', 'N/A')}\n\n")

        if "paid_advertising" in strategy:
            ads = strategy["paid_advertising"]
            f.write("## Paid Advertising\n\n")

            if ads.get("google_ads"):
                google = ads["google_ads"]
                f.write("### Google Ads\n\n")
                if google.get("campaigns"):
                    for campaign in google["campaigns"]:
                        f.write(f"**{campaign.get('name', 'Campaign')}** ({campaign.get('type', 'N/A')})\n")
                        f.write(f"- Budget: {campaign.get('budget', 'N/A')}\n")
                        if campaign.get("keywords"):
                            f.write(f"- Keywords: {', '.join(campaign['keywords'][:5])}\n")
                        f.write("\n")

                if google.get("ad_copy"):
                    f.write("**Sample Ad Copy:**\n")
                    for ad in google["ad_copy"][:3]:
                        f.write(f"- **{ad.get('headline', 'N/A')}**\n")
                        f.write(f"  {ad.get('description', 'N/A')}\n")
                        f.write(f"  CTA: {ad.get('cta', 'N/A')}\n\n")

            if ads.get("meta_ads"):
                meta = ads["meta_ads"]
                f.write("### Meta Ads (Facebook/Instagram)\n\n")
                if meta.get("audiences"):
                    f.write("**Target Audiences:**\n")
                    for aud in meta["audiences"]:
                        f.write(f"- {aud}\n")
                    f.write("\n")
                f.write(f"**Budget Allocation:** {meta.get('budget_allocation', 'N/A')}\n\n")

        if "growth_tactics" in strategy:
            growth = strategy["growth_tactics"]
            f.write("## Growth Tactics\n\n")

            if growth.get("quick_wins"):
                f.write("### Quick Wins (1-2 weeks)\n")
                for tactic in growth["quick_wins"]:
                    f.write(f"- {tactic}\n")
                f.write("\n")

            if growth.get("medium_term"):
                f.write("### Medium Term (1-3 months)\n")
                for tactic in growth["medium_term"]:
                    f.write(f"- {tactic}\n")
                f.write("\n")

            if growth.get("long_term"):
                f.write("### Long Term (3-6 months)\n")
                for tactic in growth["long_term"]:
                    f.write(f"- {tactic}\n")
                f.write("\n")

        if "metrics_to_track" in strategy:
            metrics = strategy["metrics_to_track"]
            f.write("## Success Metrics\n\n")
            for category, items in metrics.items():
                f.write(f"### {category.title()}\n")
                for item in items:
                    f.write(f"- {item}\n")
                f.write("\n")

        if "raw_response" in strategy:
            f.write("## Raw Analysis\n\n")
            f.write(strategy["raw_response"])

    print(f"Report saved to: {report_file}")

    # Save individual content pieces
    content_dir = RESULTS_DIR / "marketing_content"
    content_dir.mkdir(exist_ok=True)

    # Save ad copy as separate file
    if "paid_advertising" in strategy:
        ads = strategy["paid_advertising"]
        if ads.get("google_ads", {}).get("ad_copy"):
            ad_file = content_dir / "google_ad_copy.md"
            with open(ad_file, "w") as f:
                f.write("# Google Ads Copy\n\n")
                for ad in ads["google_ads"]["ad_copy"]:
                    f.write(f"## Ad {ads['google_ads']['ad_copy'].index(ad) + 1}\n")
                    f.write(f"**Headline:** {ad.get('headline', '')}\n\n")
                    f.write(f"**Description:** {ad.get('description', '')}\n\n")
                    f.write(f"**CTA:** {ad.get('cta', '')}\n\n---\n\n")

    # Save email templates as separate file
    if "email_campaigns" in strategy:
        email_file = content_dir / "email_templates.md"
        with open(email_file, "w") as f:
            f.write("# Email Templates\n\n")
            for seq_name, sequence in strategy["email_campaigns"].items():
                f.write(f"## {seq_name.replace('_', ' ').title()}\n\n")
                for email in sequence:
                    f.write(f"### {email.get('subject', 'Email')}\n")
                    f.write(f"**Purpose:** {email.get('purpose', 'N/A')}\n\n")
                    f.write(f"**CTA:** {email.get('cta', 'N/A')}\n\n---\n\n")

    return report_file


def main():
    """Main execution flow."""

    print("=" * 60)
    print("CLAUDE-MARKETING: AI Marketing Content Generator")
    print("=" * 60)

    RESULTS_DIR.mkdir(exist_ok=True)

    # Gather product info
    print("\nReading product information...")
    product_info = read_product_info()
    print(f"  Found {len(product_info.get('features', []))} features")

    print("Reading existing content...")
    existing_content = read_existing_content()
    print(f"  Found {len(existing_content)} content files")

    print("Analyzing competitors...")
    competitors = read_competitor_info()
    print(f"  Identified {len(competitors)} competitors")

    # Generate strategy
    strategy = generate_marketing_strategy(product_info, existing_content, competitors)

    if "error" in strategy:
        print(f"\nError: {strategy['error']}")
        return 1

    # Save output
    report_file = save_marketing_output(strategy)

    # Print summary
    print("\n" + "=" * 60)
    print("MARKETING STRATEGY COMPLETE")
    print("=" * 60)

    if "summary" in strategy:
        summary = strategy["summary"]
        print(f"Primary Channels: {', '.join(summary.get('primary_channels', []))}")
        print(f"Monthly Budget: {summary.get('estimated_monthly_budget', 'N/A')}")

    if "brand_positioning" in strategy:
        print(f"\nTagline: \"{strategy['brand_positioning'].get('tagline', 'N/A')}\"")

    if "seo_strategy" in strategy:
        keywords = strategy["seo_strategy"].get("primary_keywords", [])
        print(f"\nTop Keywords: {len(keywords)}")
        for kw in keywords[:3]:
            print(f"  - {kw.get('keyword', 'N/A')}")

    if "content_calendar" in strategy:
        posts = strategy["content_calendar"].get("blog_posts", [])
        print(f"\nBlog Posts Planned: {len(posts)}")

    print(f"\nFull strategy: {report_file}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
