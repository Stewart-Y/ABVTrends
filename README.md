# ABVTrends - Application Summary

## Overview

ABVTrends is a beverage industry price comparison and analytics platform that aggregates product data from multiple alcohol distributors. It helps retailers compare prices across distributors to find the best deals.

## Architecture

### Backend (FastAPI + Python)
- **Framework:** FastAPI with async support
- **Database:** PostgreSQL with SQLAlchemy async ORM
- **Migrations:** Alembic
- **Deployment:** AWS ECS Fargate with ECR container registry

### Frontend (Next.js + React)
- **Framework:** Next.js with TypeScript
- **Styling:** Tailwind CSS
- **Deployment:** AWS (via ALB routing)

## Implemented Distributors (6 Total)

| Distributor | Scraper Type | Status |
|-------------|--------------|--------|
| LibDib | API-based | Active |
| Park Street | Playwright browser automation | Active |
| Breakthru Beverage | Playwright with Gigya SSO auth | Active |
| Southern Glazer's (SGWS) | Browser automation | Active |
| RNDC | Browser automation | Active |
| SipMarket | Browser automation | Active |

## Key Features

### 1. Multi-Distributor Product Scraping
- Automated login and authentication for each distributor portal
- Product data extraction (name, price, SKU, brand, category, ABV, size)
- Session management for maintaining authenticated states
- Rate limiting and respectful scraping practices

### 2. Breakthru Scraper (Most Complex)
- Handles Gigya SDK (SAP Customer Identity) authentication
- Uses `bounding_box()` detection to find visible form elements among hidden duplicates
- DOM traversal from `[data-product-id]` elements to card containers
- Supports multiple product categories (Spirits, Wine, Beer)

### 3. Database Schema
- `distributors` - Registry of all supported distributors
- `products` - Unified product catalog
- `distributor_products` - Products linked to specific distributors with pricing
- `price_history` - Historical price tracking for analytics
- `users` - User accounts with email/password auth
- `api_keys` - API key authentication for programmatic access

### 4. API Endpoints
- `GET /api/v1/distributors` - List all distributors
- `POST /api/v1/distributors/{slug}/scrape` - Trigger scraping for a distributor
- `GET /api/v1/products` - Search/filter products
- `GET /api/v1/health` - Health check endpoint
- `POST /api/v1/auth/login` - User login
- `POST /api/v1/auth/register` - User registration
- `GET /api/v1/auth/me` - Get current user

### 5. Migrations (10 Total)
1. `001_distributor_tables` - Base schema
2. `002_seed_distributors` - Initial distributor data
3. `003_add_product_columns` - Extended product fields
4. `004_fix_product_metadata` - Schema fixes
5. `005_add_sipmarket_distributor` - SipMarket support
6. `006_add_parkstreet_distributor` - Park Street support
7. `007_add_breakthru_distributor` - Breakthru support
8. `008_add_remaining_distributors` - LibDib, SGWS, RNDC activation
9. `009_auth_tables` - User authentication and API keys
10. `010_users_updated_at` - Add updated_at column to users

### 6. Authentication System
- JWT-based authentication with 24-hour token expiration
- User roles: `admin` and `user`
- Password hashing with bcrypt via passlib
- API key support for programmatic access (prefix: `abv_`)
- Protected routes: Scraper page requires admin role

## Frontend Features
- Login/Register pages with form validation
- Sidebar shows user email, admin badge, and role-based navigation
- Protected route handling with automatic redirect to login
- LocalStorage token persistence (`abvtrends_token`)
- Admin-only Scraper Monitor page

## Infrastructure

### AWS Resources
- **ECS Cluster:** `abvtrends-prod-cluster`
- **ECR Repository:** `abvtrends-prod-backend`
- **RDS PostgreSQL:** `abvtrends-prod-postgres`
- **ALB:** Routes `/api/*` to backend, `/` to frontend
- **CloudWatch Logs:** `/ecs/abvtrends-prod/backend`

### Environment Configuration
- All distributor credentials stored as ECS task definition environment variables
- OpenAI API key in AWS Secrets Manager
- SSL required for production database connections

### CI/CD Pipeline
- GitHub Actions workflows for automated deployment
- Docker image builds with GitHub Actions cache
- Automated database migrations run before service deployment
- Health checks after deployment
- AI Deploy Decider agent for deployment approval

## Testing
- Playwright E2E tests for authentication flows
- Backend unit tests for auth services (password hashing, JWT, API keys)
- AI-powered deploy gatekeeper that analyzes commits before deployment

## Technical Highlights
- **Async throughout:** All database operations and HTTP requests use async/await
- **Playwright for complex sites:** Browser automation for JavaScript-heavy distributor portals
- **Graceful error handling:** Scrapers continue on individual product failures
- **Session persistence:** Maintains login sessions to avoid repeated authentication
- **Docker multi-platform builds:** `linux/amd64` for ECS Fargate compatibility

## Known Constraints
- `bcrypt` pinned to 4.2.0 (5.0.0+ has breaking changes with passlib)
- SSL verification relaxed for AWS RDS connections
