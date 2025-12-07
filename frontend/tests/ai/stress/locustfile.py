#!/usr/bin/env python3
"""
ABVTrends Backend Stress Testing with Locust

AI-guided load testing for the ABVTrends API.
Run with: locust -f locustfile.py --host=http://localhost:8000
"""

from locust import HttpUser, task, between, events
import json
import random
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ABVTrendsUser(HttpUser):
    """Simulates a typical ABVTrends user browsing the platform."""

    wait_time = between(1, 3)  # Wait 1-3 seconds between requests

    # Store discovered product IDs for realistic navigation
    product_ids = []
    categories = ["spirits", "wine", "beer", "liqueur"]
    tiers = ["viral", "rising", "emerging", "stable"]

    def on_start(self):
        """Called when a simulated user starts."""
        # Fetch initial products to get real IDs
        try:
            response = self.client.get("/api/v1/products?limit=20")
            if response.status_code == 200:
                data = response.json()
                if "data" in data:
                    self.product_ids = [p.get("id") for p in data["data"] if p.get("id")]
        except Exception as e:
            logger.warning(f"Could not fetch initial products: {e}")

    # ==================== Core API Endpoints ====================

    @task(10)
    def get_trends(self):
        """Most common request - fetch trending products."""
        self.client.get("/api/v1/trends")

    @task(8)
    def get_trends_paginated(self):
        """Paginated trends with random page."""
        page = random.randint(1, 5)
        limit = random.choice([10, 20, 50])
        self.client.get(f"/api/v1/trends?page={page}&limit={limit}")

    @task(6)
    def get_trends_filtered(self):
        """Filtered trends by category and tier."""
        category = random.choice(self.categories)
        tier = random.choice(self.tiers)
        self.client.get(f"/api/v1/trends?category={category}&tier={tier}")

    @task(5)
    def get_top_trends(self):
        """Get top trends by tier."""
        tier = random.choice(self.tiers)
        self.client.get(f"/api/v1/trends/top?tier={tier}&limit=10")

    # ==================== Products Endpoints ====================

    @task(8)
    def get_products(self):
        """Fetch products list."""
        self.client.get("/api/v1/products")

    @task(5)
    def get_products_paginated(self):
        """Paginated products."""
        page = random.randint(1, 5)
        self.client.get(f"/api/v1/products?page={page}&limit=20")

    @task(4)
    def get_product_detail(self):
        """Get specific product details."""
        if self.product_ids:
            product_id = random.choice(self.product_ids)
            self.client.get(f"/api/v1/products/{product_id}")

    @task(3)
    def get_categories(self):
        """Fetch category list."""
        self.client.get("/api/v1/products/categories/list")

    @task(3)
    def search_products(self):
        """Search products by name."""
        search_terms = ["vodka", "whiskey", "tequila", "rum", "gin", "wine"]
        term = random.choice(search_terms)
        self.client.get(f"/api/v1/products?search={term}")

    # ==================== Discover Endpoints ====================

    @task(4)
    def get_new_arrivals(self):
        """Fetch new arrivals."""
        self.client.get("/api/v1/products/discover/new-arrivals?limit=10")

    @task(3)
    def get_celebrity_bottles(self):
        """Fetch celebrity-affiliated products."""
        self.client.get("/api/v1/products/discover/celebrity?limit=10")

    @task(3)
    def get_early_movers(self):
        """Fetch early mover products."""
        self.client.get("/api/v1/products/discover/early-movers?limit=10")

    # ==================== Forecast Endpoints ====================

    @task(2)
    def get_forecast(self):
        """Get trend forecast for a product."""
        if self.product_ids:
            product_id = random.choice(self.product_ids)
            self.client.get(f"/api/v1/forecasts/{product_id}")

    # ==================== Health Check ====================

    @task(1)
    def health_check(self):
        """API health check."""
        self.client.get("/health")


class ABVTrendsAdminUser(HttpUser):
    """Simulates admin/power user behavior with heavier requests."""

    wait_time = between(2, 5)
    weight = 1  # Less common than regular users

    @task(5)
    def get_all_trends_large(self):
        """Large paginated request."""
        self.client.get("/api/v1/trends?limit=100")

    @task(3)
    def get_scraper_status(self):
        """Check scraper status."""
        self.client.get("/api/v1/scraper/status")

    @task(2)
    def get_scraper_logs(self):
        """Fetch scraper logs."""
        self.client.get("/api/v1/scraper/logs?limit=50")

    @task(1)
    def get_scheduler_status(self):
        """Check scheduler status."""
        self.client.get("/api/v1/scheduler/status")


class ABVTrendsBurstUser(HttpUser):
    """Simulates burst traffic patterns."""

    wait_time = between(0.1, 0.5)  # Very fast requests
    weight = 1  # Rare but intense

    @task
    def burst_trends(self):
        """Rapid-fire trends requests."""
        for _ in range(5):
            self.client.get("/api/v1/trends")

    @task
    def burst_products(self):
        """Rapid-fire products requests."""
        for _ in range(5):
            self.client.get("/api/v1/products")


# ==================== Event Hooks for Reporting ====================

@events.request.add_listener
def on_request(request_type, name, response_time, response_length, response, context, exception, **kwargs):
    """Log slow requests for analysis."""
    if response_time > 1000:  # Requests over 1 second
        logger.warning(f"SLOW REQUEST: {request_type} {name} took {response_time}ms")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Generate summary report at test end."""
    stats = environment.stats
    logger.info("=" * 60)
    logger.info("STRESS TEST SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total requests: {stats.total.num_requests}")
    logger.info(f"Failed requests: {stats.total.num_failures}")
    logger.info(f"Average response time: {stats.total.avg_response_time:.2f}ms")
    logger.info(f"Median response time: {stats.total.median_response_time}ms")
    logger.info(f"95th percentile: {stats.total.get_response_time_percentile(0.95)}ms")
    logger.info(f"99th percentile: {stats.total.get_response_time_percentile(0.99)}ms")
    logger.info(f"Requests/sec: {stats.total.total_rps:.2f}")
    logger.info("=" * 60)


# ==================== AI Analysis Integration ====================

def generate_ai_report(stats_json_path: str) -> str:
    """
    Generate AI-powered analysis of load test results.
    Call this after running: locust --csv=results --headless -t 5m
    """
    import os
    try:
        from anthropic import Anthropic
    except ImportError:
        return "anthropic package not installed"

    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    with open(stats_json_path) as f:
        stats = json.load(f)

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4000,
        system="""You are a performance engineering expert analyzing load test results.
        Identify bottlenecks, suggest optimizations, and recommend database indexes or caching strategies.""",
        messages=[{
            "role": "user",
            "content": f"Analyze these load test results and provide recommendations:\n{json.dumps(stats, indent=2)}"
        }]
    )

    return response.content[0].text


if __name__ == "__main__":
    print("""
ABVTrends Stress Testing with Locust

Usage:
  # Web UI mode (recommended for exploration)
  locust -f locustfile.py --host=http://localhost:8000

  # Headless mode (for CI/CD)
  locust -f locustfile.py --host=http://localhost:8000 --headless -u 100 -r 10 -t 5m

  # With CSV export
  locust -f locustfile.py --host=http://localhost:8000 --headless -u 100 -r 10 -t 5m --csv=results

Parameters:
  -u, --users: Number of concurrent users
  -r, --spawn-rate: Users to spawn per second
  -t, --run-time: Test duration (e.g., 5m, 1h)
  --csv: Export results to CSV files
""")
