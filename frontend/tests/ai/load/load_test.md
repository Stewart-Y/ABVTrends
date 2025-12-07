# ABVTrends Load Testing Configuration

This document defines load testing parameters that Claude can adjust based on infrastructure capacity.

## Test Scenarios

### Scenario 1: Normal Traffic
Simulates typical daily usage patterns.

```yaml
users: 50
spawn_rate: 5
duration: 10m
endpoints:
  - GET /api/v1/trends (weight: 10)
  - GET /api/v1/products (weight: 8)
  - GET /api/v1/trends/top (weight: 5)
  - GET /api/v1/products/{id} (weight: 4)
```

### Scenario 2: Peak Traffic
Simulates high-traffic periods (marketing campaigns, viral events).

```yaml
users: 200
spawn_rate: 20
duration: 15m
endpoints:
  - GET /api/v1/trends (weight: 15)
  - GET /api/v1/products (weight: 10)
  - GET /api/v1/products/discover/new-arrivals (weight: 8)
  - GET /api/v1/trends?category=spirits (weight: 6)
```

### Scenario 3: Stress Test
Push the system to find breaking points.

```yaml
users: 500
spawn_rate: 50
duration: 20m
ramp_up: true
endpoints:
  - GET /api/v1/trends (weight: 10)
  - GET /api/v1/products (weight: 10)
  - GET /api/v1/forecasts/{id} (weight: 5)
```

### Scenario 4: Sustained Load
Long-running test to detect memory leaks and degradation.

```yaml
users: 100
spawn_rate: 10
duration: 1h
endpoints:
  - GET /api/v1/trends (weight: 10)
  - GET /api/v1/products (weight: 8)
  - GET /api/v1/products/categories/list (weight: 3)
```

### Scenario 5: Burst Traffic
Sudden traffic spikes.

```yaml
phases:
  - users: 10, duration: 2m  # Warm up
  - users: 300, duration: 1m  # Burst
  - users: 10, duration: 2m  # Cool down
  - users: 500, duration: 1m  # Major burst
  - users: 10, duration: 2m  # Recovery
```

## Performance Targets

### Response Time SLAs
| Endpoint Pattern | p50 | p95 | p99 |
|-----------------|-----|-----|-----|
| GET /api/v1/trends | <100ms | <300ms | <500ms |
| GET /api/v1/products | <100ms | <300ms | <500ms |
| GET /api/v1/products/{id} | <50ms | <150ms | <300ms |
| GET /api/v1/forecasts/{id} | <200ms | <500ms | <1000ms |
| POST /api/v1/scraper/* | <500ms | <1000ms | <2000ms |

### Throughput Targets
- Minimum: 100 requests/second
- Target: 500 requests/second
- Peak: 1000 requests/second

### Error Rate Targets
- Normal: <0.1%
- Peak: <1%
- Stress: <5%

## Infrastructure Recommendations

### Database
- Connection pool size: 20-50 connections
- Query timeout: 5 seconds
- Indexes recommended:
  - `trends.trend_tier` (filter queries)
  - `trends.score` (sorting)
  - `products.category` (filter queries)
  - `products.name` (search queries - GIN index)

### Caching
- Redis recommended for:
  - Top trends (TTL: 5 minutes)
  - Category list (TTL: 1 hour)
  - Product details (TTL: 10 minutes)

### Application
- Workers: 4-8 per CPU core
- Request timeout: 30 seconds
- Keep-alive connections: enabled

## Running Load Tests

```bash
# Normal traffic test
locust -f tests/ai/stress/locustfile.py \
  --host=http://localhost:8000 \
  --headless -u 50 -r 5 -t 10m \
  --csv=results/normal_traffic

# Peak traffic test
locust -f tests/ai/stress/locustfile.py \
  --host=http://localhost:8000 \
  --headless -u 200 -r 20 -t 15m \
  --csv=results/peak_traffic

# Stress test
locust -f tests/ai/stress/locustfile.py \
  --host=http://localhost:8000 \
  --headless -u 500 -r 50 -t 20m \
  --csv=results/stress_test
```

## AI Analysis Triggers

Claude should analyze load test results when:
1. p95 latency exceeds SLA by >50%
2. Error rate exceeds target by >2x
3. Throughput drops below minimum
4. Memory usage exceeds 80%
5. CPU usage sustained >90%

## Optimization Recommendations Template

When analyzing results, Claude should provide:
1. **Bottleneck Identification**: Which endpoints are slow and why
2. **Database Optimization**: Query improvements, index suggestions
3. **Caching Strategy**: What to cache and for how long
4. **Scaling Recommendations**: Horizontal vs vertical scaling
5. **Code Improvements**: Specific code changes to improve performance
