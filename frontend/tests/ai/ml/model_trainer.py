#!/usr/bin/env python3
"""
CLAUDE-ML-TRAINER: AI Model Training Advisor

Analyzes ML model performance and provides:
- Model drift detection
- Retraining recommendations
- Hyperparameter suggestions
- Feature engineering improvements
- Model selection advice
- Training code generation
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
You are CLAUDE-ML-TRAINER, an expert machine learning engineer.

You analyze ML models and provide training recommendations.

Analysis Areas:

1. **Model Performance**
   - Accuracy, precision, recall, F1
   - RMSE, MAE for regression
   - AUC-ROC for classification
   - Custom business metrics

2. **Model Drift Detection**
   - Data drift (feature distribution changes)
   - Concept drift (target relationship changes)
   - Label drift
   - Performance degradation over time

3. **Retraining Strategy**
   - When to retrain (triggers)
   - Incremental vs full retraining
   - A/B testing new models
   - Canary deployments

4. **Hyperparameter Optimization**
   - Grid search vs Bayesian optimization
   - Learning rate schedules
   - Regularization parameters
   - Architecture choices

5. **Feature Engineering**
   - Feature importance analysis
   - New feature suggestions
   - Feature selection
   - Embedding strategies

6. **Model Selection**
   - Algorithm comparison
   - Ensemble methods
   - Deep learning vs traditional ML
   - AutoML recommendations

ABVTrends Context:
- Trend score forecasting (regression)
- Time series prediction
- Signal strength analysis
- Product trend classification

Output Format (JSON):
{
  "summary": {
    "model_health": "healthy|degrading|needs_retraining",
    "drift_detected": true/false,
    "recommended_action": "...",
    "priority": "high|medium|low"
  },
  "current_model": {
    "type": "...",
    "metrics": {
      "rmse": 0.0,
      "mae": 0.0,
      "r2": 0.0
    },
    "last_trained": "...",
    "features_used": []
  },
  "drift_analysis": {
    "data_drift": {"detected": true/false, "features": ["..."]},
    "concept_drift": {"detected": true/false, "severity": "..."},
    "performance_trend": "improving|stable|degrading"
  },
  "recommendations": {
    "immediate": ["..."],
    "short_term": ["..."],
    "long_term": ["..."]
  },
  "retraining_plan": {
    "trigger": "...",
    "approach": "incremental|full",
    "data_requirements": "...",
    "estimated_improvement": "..."
  },
  "hyperparameters": {
    "current": {},
    "suggested": {},
    "search_space": {}
  },
  "feature_engineering": {
    "important_features": [],
    "suggested_new_features": [],
    "features_to_remove": []
  },
  "model_alternatives": [
    {
      "model": "...",
      "pros": ["..."],
      "cons": ["..."],
      "expected_improvement": "..."
    }
  ],
  "training_code": "Python code for retraining..."
}
"""


def read_ml_code() -> dict:
    """Read ML-related code from the project."""

    ml_code = {}

    # Look for ML/forecasting related files
    patterns = ["*forecast*", "*predict*", "*model*", "*ml*", "*trend*"]

    for pattern in patterns:
        for file in BACKEND_DIR.rglob(f"{pattern}.py"):
            if any(x in str(file) for x in ["__pycache__", "venv"]):
                continue
            try:
                ml_code[str(file.relative_to(PROJECT_ROOT))] = file.read_text()
            except:
                pass

    # Also check services directory
    services_dir = BACKEND_DIR / "app" / "services"
    if services_dir.exists():
        for file in services_dir.glob("*.py"):
            try:
                content = file.read_text()
                if any(kw in content.lower() for kw in ["predict", "forecast", "model", "sklearn", "torch"]):
                    ml_code[str(file.relative_to(PROJECT_ROOT))] = content
            except:
                pass

    return ml_code


def read_model_metrics() -> dict:
    """Read any existing model metrics/reports."""

    metrics = {}

    # Look for model-related reports
    report_patterns = [
        "model_*.json",
        "forecast_*.json",
        "metrics_*.json",
        "*drift*.json"
    ]

    for pattern in report_patterns:
        for file in RESULTS_DIR.glob(pattern):
            try:
                with open(file) as f:
                    metrics[file.name] = json.load(f)
            except:
                pass

    return metrics


def analyze_ml_models(ml_code: dict, metrics: dict) -> dict:
    """Analyze ML models with Claude."""

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {"error": "ANTHROPIC_API_KEY not set"}

    print("Analyzing ML models...")

    # Build code summary
    code_summary = ""
    for path, content in ml_code.items():
        code_summary += f"\n### {path}\n```python\n{content[:3000]}\n```\n"

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=10000,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"""
Analyze the ML models in this trend forecasting platform.

## Project: ABVTrends
An AI-powered alcohol trend forecasting platform that:
- Predicts trend scores for alcohol products
- Forecasts future popularity
- Analyzes signal strength from various sources
- Classifies products into trend tiers

## ML-Related Code ({len(ml_code)} files)
{code_summary[:25000]}

## Existing Model Metrics
{json.dumps(metrics, indent=2, default=str)[:5000]}

Please analyze and provide:
1. Current model health assessment
2. Drift detection analysis
3. Retraining recommendations
4. Hyperparameter suggestions
5. Feature engineering opportunities
6. Alternative model recommendations
7. Python code for retraining

If no ML code exists, recommend how to implement:
- Trend score forecasting model
- Time series prediction
- Feature pipeline
- Model serving infrastructure

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


def save_ml_report(analysis: dict):
    """Save ML analysis report."""

    RESULTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save JSON
    json_file = RESULTS_DIR / f"ml_analysis_{timestamp}.json"
    with open(json_file, "w") as f:
        json.dump(analysis, f, indent=2)

    # Save markdown report
    report_file = RESULTS_DIR / "model_retrain_plan.md"
    with open(report_file, "w") as f:
        f.write("# ML Model Analysis & Retraining Plan\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")

        if "summary" in analysis:
            summary = analysis["summary"]
            health_emoji = {
                "healthy": "✅",
                "degrading": "⚠️",
                "needs_retraining": "🔴"
            }.get(summary.get("model_health"), "❓")

            f.write("## Summary\n\n")
            f.write(f"- **Model Health:** {health_emoji} {summary.get('model_health', 'N/A')}\n")
            f.write(f"- **Drift Detected:** {'Yes' if summary.get('drift_detected') else 'No'}\n")
            f.write(f"- **Recommended Action:** {summary.get('recommended_action', 'N/A')}\n")
            f.write(f"- **Priority:** {summary.get('priority', 'N/A')}\n\n")

        if "current_model" in analysis:
            model = analysis["current_model"]
            f.write("## Current Model\n\n")
            f.write(f"- **Type:** {model.get('type', 'N/A')}\n")
            f.write(f"- **Last Trained:** {model.get('last_trained', 'N/A')}\n\n")

            if model.get("metrics"):
                f.write("### Metrics\n")
                for metric, value in model["metrics"].items():
                    f.write(f"- **{metric.upper()}:** {value}\n")
                f.write("\n")

        if "drift_analysis" in analysis:
            drift = analysis["drift_analysis"]
            f.write("## Drift Analysis\n\n")

            if drift.get("data_drift"):
                data_drift = drift["data_drift"]
                f.write(f"- **Data Drift:** {'Detected' if data_drift.get('detected') else 'Not Detected'}\n")
                if data_drift.get("features"):
                    f.write(f"  - Affected features: {', '.join(data_drift['features'])}\n")

            if drift.get("concept_drift"):
                concept_drift = drift["concept_drift"]
                f.write(f"- **Concept Drift:** {'Detected' if concept_drift.get('detected') else 'Not Detected'}\n")

            f.write(f"- **Performance Trend:** {drift.get('performance_trend', 'N/A')}\n\n")

        if "recommendations" in analysis:
            recs = analysis["recommendations"]
            f.write("## Recommendations\n\n")

            if recs.get("immediate"):
                f.write("### Immediate Actions\n")
                for rec in recs["immediate"]:
                    f.write(f"- {rec}\n")
                f.write("\n")

            if recs.get("short_term"):
                f.write("### Short-term Improvements\n")
                for rec in recs["short_term"]:
                    f.write(f"- {rec}\n")
                f.write("\n")

            if recs.get("long_term"):
                f.write("### Long-term Strategy\n")
                for rec in recs["long_term"]:
                    f.write(f"- {rec}\n")
                f.write("\n")

        if "retraining_plan" in analysis:
            plan = analysis["retraining_plan"]
            f.write("## Retraining Plan\n\n")
            f.write(f"- **Trigger:** {plan.get('trigger', 'N/A')}\n")
            f.write(f"- **Approach:** {plan.get('approach', 'N/A')}\n")
            f.write(f"- **Data Requirements:** {plan.get('data_requirements', 'N/A')}\n")
            f.write(f"- **Expected Improvement:** {plan.get('estimated_improvement', 'N/A')}\n\n")

        if "feature_engineering" in analysis:
            features = analysis["feature_engineering"]
            f.write("## Feature Engineering\n\n")

            if features.get("important_features"):
                f.write("### Important Features\n")
                for feat in features["important_features"]:
                    f.write(f"- {feat}\n")
                f.write("\n")

            if features.get("suggested_new_features"):
                f.write("### Suggested New Features\n")
                for feat in features["suggested_new_features"]:
                    f.write(f"- {feat}\n")
                f.write("\n")

        if "model_alternatives" in analysis:
            f.write("## Alternative Models\n\n")
            for alt in analysis["model_alternatives"]:
                f.write(f"### {alt.get('model', 'Unknown')}\n")
                f.write(f"**Expected Improvement:** {alt.get('expected_improvement', 'N/A')}\n\n")
                if alt.get("pros"):
                    f.write("**Pros:**\n")
                    for pro in alt["pros"]:
                        f.write(f"- {pro}\n")
                if alt.get("cons"):
                    f.write("\n**Cons:**\n")
                    for con in alt["cons"]:
                        f.write(f"- {con}\n")
                f.write("\n")

        if "training_code" in analysis:
            f.write("## Training Code\n\n")
            f.write("```python\n")
            f.write(analysis["training_code"])
            f.write("\n```\n")

        if "raw_response" in analysis:
            f.write("## Raw Analysis\n\n")
            f.write(analysis["raw_response"])

    print(f"Report saved to: {report_file}")

    # Save training code separately if exists
    if "training_code" in analysis:
        code_file = RESULTS_DIR / f"generated_training_{timestamp}.py"
        with open(code_file, "w") as f:
            f.write("#!/usr/bin/env python3\n")
            f.write('"""Generated ML training code."""\n\n')
            f.write(analysis["training_code"])
        print(f"Training code saved to: {code_file}")

    return report_file


def main():
    """Main execution flow."""

    print("=" * 60)
    print("CLAUDE-ML-TRAINER: AI Model Training Advisor")
    print("=" * 60)

    RESULTS_DIR.mkdir(exist_ok=True)

    # Read ML code
    print("\nScanning for ML-related code...")
    ml_code = read_ml_code()
    print(f"  Found {len(ml_code)} ML-related files")

    # Read existing metrics
    print("Reading model metrics...")
    metrics = read_model_metrics()
    print(f"  Found {len(metrics)} metric files")

    # Analyze
    analysis = analyze_ml_models(ml_code, metrics)

    if "error" in analysis:
        print(f"\nError: {analysis['error']}")
        return 1

    # Save report
    report_file = save_ml_report(analysis)

    # Print summary
    print("\n" + "=" * 60)
    print("ML ANALYSIS COMPLETE")
    print("=" * 60)

    if "summary" in analysis:
        summary = analysis["summary"]
        print(f"Model Health: {summary.get('model_health', 'N/A')}")
        print(f"Drift Detected: {'Yes' if summary.get('drift_detected') else 'No'}")
        print(f"Priority: {summary.get('priority', 'N/A')}")
        print(f"Action: {summary.get('recommended_action', 'N/A')}")

    print(f"\nFull report: {report_file}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
