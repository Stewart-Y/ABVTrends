#!/usr/bin/env python3
"""
CLAUDE-UX: AI UX Testing Agent

Evaluates UI/UX by:
- Taking screenshots of pages
- Analyzing usability heuristics
- Detecting confusing flows
- Recommending UX improvements
- Suggesting new UI components
- Providing wireframe ideas
"""

import os
import sys
import re
import json
import base64
from datetime import datetime
from pathlib import Path

# Setup paths
SCRIPT_DIR = Path(__file__).parent
ROOT_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = ROOT_DIR.parent.parent.parent
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
You are CLAUDE-UX, an expert UX designer and usability analyst.

You evaluate UI/UX based on:

1. **Nielsen's 10 Usability Heuristics**
   - Visibility of system status
   - Match between system and real world
   - User control and freedom
   - Consistency and standards
   - Error prevention
   - Recognition rather than recall
   - Flexibility and efficiency
   - Aesthetic and minimalist design
   - Help users recognize, diagnose, recover from errors
   - Help and documentation

2. **Visual Design Principles**
   - Color contrast and accessibility (WCAG)
   - Typography hierarchy
   - Spacing and alignment
   - Visual hierarchy
   - Brand consistency

3. **Interaction Design**
   - Click targets (min 44x44px)
   - Loading states
   - Error states
   - Empty states
   - Hover/focus states

4. **Information Architecture**
   - Navigation clarity
   - Content organization
   - Labeling
   - Search and filtering

5. **Mobile Responsiveness**
   - Touch-friendly design
   - Responsive layout
   - Mobile-first considerations

ABVTrends Context:
- Alcohol trend forecasting platform
- Dashboard with trend cards
- Data tables with filtering
- Product detail pages with charts
- Target users: beverage buyers, distributors

Output Format (JSON):
{
  "overall_score": 0-100,
  "heuristic_scores": {
    "visibility": 0-10,
    "real_world_match": 0-10,
    ...
  },
  "issues": [
    {
      "severity": "critical|high|medium|low",
      "category": "usability|visual|interaction|accessibility",
      "location": "page/component",
      "description": "What's wrong",
      "recommendation": "How to fix",
      "wireframe": "ASCII wireframe suggestion (optional)"
    }
  ],
  "strengths": ["..."],
  "recommendations": [
    {
      "priority": "high|medium|low",
      "category": "...",
      "description": "...",
      "implementation": "..."
    }
  ]
}
"""


def capture_screenshots() -> list:
    """Capture screenshots of app pages using Playwright."""

    screenshots = []

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright not installed. Run: pip install playwright && playwright install")
        return screenshots

    pages_to_capture = [
        ("http://localhost:3000", "dashboard"),
        ("http://localhost:3000/trends", "trends"),
        ("http://localhost:3000/discover", "discover"),
        ("http://localhost:3000/scraper", "scraper"),
    ]

    print("Capturing screenshots...")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1920, "height": 1080})
            page = context.new_page()

            for url, name in pages_to_capture:
                try:
                    page.goto(url, timeout=10000)
                    page.wait_for_load_state("networkidle", timeout=5000)

                    # Capture full page screenshot
                    screenshot_bytes = page.screenshot(full_page=True)
                    screenshot_b64 = base64.standard_b64encode(screenshot_bytes).decode("utf-8")

                    screenshots.append({
                        "name": name,
                        "url": url,
                        "screenshot_b64": screenshot_b64,
                        "viewport": {"width": 1920, "height": 1080}
                    })
                    print(f"  Captured: {name}")

                except Exception as e:
                    print(f"  Failed to capture {name}: {e}")

            # Also capture mobile viewport
            context_mobile = browser.new_context(viewport={"width": 375, "height": 812})
            page_mobile = context_mobile.new_page()

            try:
                page_mobile.goto("http://localhost:3000", timeout=10000)
                page_mobile.wait_for_load_state("networkidle", timeout=5000)

                screenshot_bytes = page_mobile.screenshot(full_page=True)
                screenshot_b64 = base64.standard_b64encode(screenshot_bytes).decode("utf-8")

                screenshots.append({
                    "name": "dashboard_mobile",
                    "url": "http://localhost:3000",
                    "screenshot_b64": screenshot_b64,
                    "viewport": {"width": 375, "height": 812}
                })
                print(f"  Captured: dashboard_mobile")

            except Exception as e:
                print(f"  Failed to capture mobile: {e}")

            browser.close()

    except Exception as e:
        print(f"Playwright error: {e}")

    return screenshots


def read_frontend_code() -> dict:
    """Read frontend code for context."""

    code_context = {}

    # Read key pages
    pages_dir = FRONTEND_DIR / "pages"
    if pages_dir.exists():
        for file in pages_dir.glob("*.tsx"):
            if file.name not in ["_app.tsx", "_document.tsx"]:
                try:
                    content = file.read_text()[:3000]
                    code_context[file.name] = content
                except:
                    pass

    # Read components
    components_dir = FRONTEND_DIR / "components"
    if components_dir.exists():
        for file in components_dir.glob("*.tsx"):
            try:
                content = file.read_text()[:2000]
                code_context[f"components/{file.name}"] = content
            except:
                pass

    # Read styles
    styles_file = FRONTEND_DIR / "styles" / "globals.css"
    if styles_file.exists():
        try:
            code_context["styles/globals.css"] = styles_file.read_text()[:2000]
        except:
            pass

    return code_context


def analyze_ux(screenshots: list, code_context: dict) -> dict:
    """Analyze UX with Claude."""

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {"error": "ANTHROPIC_API_KEY not set"}

    print("Analyzing UX with Claude...")

    # Build message content with screenshots
    message_content = []

    # Add text context
    text_context = f"""
Analyze the UX of ABVTrends application.

## Frontend Code Context
{json.dumps(list(code_context.keys()), indent=2)}

## Key Components
"""
    for name, code in list(code_context.items())[:3]:
        text_context += f"\n### {name}\n```tsx\n{code[:1500]}\n```\n"

    message_content.append({
        "type": "text",
        "text": text_context
    })

    # Add screenshots as images
    for screenshot in screenshots[:4]:  # Limit to 4 screenshots
        message_content.append({
            "type": "text",
            "text": f"\n## Screenshot: {screenshot['name']} ({screenshot['viewport']['width']}x{screenshot['viewport']['height']})\n"
        })
        message_content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": screenshot["screenshot_b64"]
            }
        })

    message_content.append({
        "type": "text",
        "text": """
Please analyze the UX and provide:
1. Overall UX score (0-100)
2. Heuristic evaluation scores
3. Issues found with severity and recommendations
4. Strengths of the current design
5. Priority recommendations for improvement
6. ASCII wireframe suggestions for key improvements

Return your analysis as JSON.
"""
    })

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": message_content
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


def analyze_without_screenshots(code_context: dict) -> dict:
    """Analyze UX from code only when screenshots unavailable."""

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {"error": "ANTHROPIC_API_KEY not set"}

    print("Analyzing UX from code (no screenshots available)...")

    code_summary = ""
    for name, code in code_context.items():
        code_summary += f"\n### {name}\n```tsx\n{code}\n```\n"

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"""
Analyze the UX of ABVTrends based on the frontend code.
(Note: Screenshots unavailable - analyzing code structure only)

## Frontend Code
{code_summary[:15000]}

Please analyze and provide:
1. Code-based UX assessment
2. Potential usability issues inferred from code
3. Accessibility concerns from code review
4. Recommendations for improvement
5. Missing UX patterns that should be added

Return your analysis as JSON.
"""
                }
            ]
        )

        content = response.content[0].text

        try:
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

        return {"raw_response": content}

    except Exception as e:
        return {"error": str(e)}


def save_ux_report(analysis: dict, screenshots: list):
    """Save UX analysis report."""

    RESULTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save JSON
    json_file = RESULTS_DIR / f"ux_analysis_{timestamp}.json"
    with open(json_file, "w") as f:
        # Don't include screenshot data in JSON
        analysis_copy = {k: v for k, v in analysis.items() if k != "raw_response"}
        json.dump(analysis_copy, f, indent=2)

    # Save markdown report
    report_file = RESULTS_DIR / "ux_report.md"
    with open(report_file, "w") as f:
        f.write("# UX Analysis Report\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")

        if "overall_score" in analysis:
            f.write(f"## Overall UX Score: {analysis['overall_score']}/100\n\n")

        if "heuristic_scores" in analysis:
            f.write("## Heuristic Scores\n\n")
            f.write("| Heuristic | Score |\n|-----------|-------|\n")
            for heuristic, score in analysis["heuristic_scores"].items():
                f.write(f"| {heuristic.replace('_', ' ').title()} | {score}/10 |\n")
            f.write("\n")

        if "strengths" in analysis:
            f.write("## Strengths\n\n")
            for strength in analysis["strengths"]:
                f.write(f"- {strength}\n")
            f.write("\n")

        if "issues" in analysis:
            f.write("## Issues Found\n\n")
            for issue in analysis["issues"]:
                severity = issue.get("severity", "medium")
                f.write(f"### [{severity.upper()}] {issue.get('category', 'General')}\n")
                f.write(f"**Location:** {issue.get('location', 'N/A')}\n\n")
                f.write(f"{issue.get('description', 'N/A')}\n\n")
                f.write(f"**Recommendation:** {issue.get('recommendation', 'N/A')}\n\n")
                if issue.get("wireframe"):
                    f.write(f"**Wireframe Suggestion:**\n```\n{issue['wireframe']}\n```\n\n")

        if "recommendations" in analysis:
            f.write("## Recommendations\n\n")
            for rec in analysis["recommendations"]:
                priority = rec.get("priority", "medium")
                f.write(f"### [{priority.upper()}] {rec.get('category', 'General')}\n")
                f.write(f"{rec.get('description', 'N/A')}\n\n")
                if rec.get("implementation"):
                    f.write(f"**Implementation:** {rec['implementation']}\n\n")

        if "raw_response" in analysis:
            f.write("## Raw Analysis\n\n")
            f.write(analysis["raw_response"])

    print(f"UX report saved to: {report_file}")

    # Save screenshots if captured
    if screenshots:
        screenshots_dir = RESULTS_DIR / "ux_screenshots"
        screenshots_dir.mkdir(exist_ok=True)
        for screenshot in screenshots:
            img_file = screenshots_dir / f"{screenshot['name']}.png"
            img_bytes = base64.standard_b64decode(screenshot["screenshot_b64"])
            with open(img_file, "wb") as f:
                f.write(img_bytes)
        print(f"Screenshots saved to: {screenshots_dir}")

    return report_file


def main():
    """Main execution flow."""

    print("=" * 60)
    print("CLAUDE-UX: AI UX Testing Agent")
    print("=" * 60)

    RESULTS_DIR.mkdir(exist_ok=True)

    # Capture screenshots
    screenshots = capture_screenshots()

    # Read frontend code
    print("\nReading frontend code...")
    code_context = read_frontend_code()
    print(f"  Found {len(code_context)} files")

    # Analyze UX
    if screenshots:
        analysis = analyze_ux(screenshots, code_context)
    else:
        print("\nNo screenshots captured - analyzing code only")
        analysis = analyze_without_screenshots(code_context)

    if "error" in analysis:
        print(f"\nError: {analysis['error']}")
        return 1

    # Save report
    report_file = save_ux_report(analysis, screenshots)

    # Print summary
    print("\n" + "=" * 60)
    print("UX ANALYSIS COMPLETE")
    print("=" * 60)

    if "overall_score" in analysis:
        print(f"Overall UX Score: {analysis['overall_score']}/100")

    if "issues" in analysis:
        critical = len([i for i in analysis["issues"] if i.get("severity") == "critical"])
        high = len([i for i in analysis["issues"] if i.get("severity") == "high"])
        print(f"Issues found: {len(analysis['issues'])} ({critical} critical, {high} high)")

    print(f"\nFull report: {report_file}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
