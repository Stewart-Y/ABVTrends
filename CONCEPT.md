# ABVTrends

## Concept

ABVTrends is an AI-powered analytics platform that tracks and predicts trends in the alcohol beverage industry. It aggregates signals from media coverage, retail availability, and industry news to generate real-time trend scores for spirits, wine, beer, and RTD products.

The platform helps industry professionals, investors, and enthusiasts identify emerging products before they go mainstream, track viral sensations, and understand market movements through data-driven insights.

## Core Features

### Trend Scoring Engine
- Composite scoring algorithm (0-100) based on multiple signal types
- Tier classification: Viral (90+), Trending (70-89), Emerging (50-69), Stable (30-49), Declining (<30)
- Component breakdown: Media, Social, Retail, Price, Search, Seasonal factors

### AI-Powered Data Collection
- Automated scraping of 20+ media sources (VinePair, Liquor.com, BevNET, etc.)
- OpenAI-powered article analysis and product extraction
- Retail availability tracking from major distributors

### Analytics Dashboard
- Real-time trend monitoring
- Product discovery (New Arrivals, Celebrity Bottles, Early Movers)
- Historical trend data and forecasting

## Currently Implemented

### Backend (FastAPI)
- REST API with full CRUD operations
- PostgreSQL database with async support
- AI scraper with configurable sources
- Trend calculation engine
- Scheduler for automated data collection

### Frontend (Next.js)
- Dashboard with KPI cards and trend sections
- Trends Explorer with filtering and search
- Product detail pages with score breakdowns
- Scraper control panel
- Discover page for product exploration

### Infrastructure (AWS)
- ECS Fargate for containerized services
- RDS PostgreSQL database
- Application Load Balancer with HTTPS
- ECR for container registry
- Secrets Manager for API keys
- Route 53 DNS (abvtrends.com)
- GitHub Actions CI/CD pipeline

### Testing
- Playwright E2E test suite
- API integration tests
