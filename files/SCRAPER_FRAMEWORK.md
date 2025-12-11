# ABVTrends Scraper Framework

## Overview

The scraper framework provides a unified interface for collecting data from multiple sources:
- **Distributor scrapers**: LibDib, SGWS, RNDC, Provi, Breakthru, Park Street, etc.
- **Media scrapers**: VinePair, Liquor.com, BevNET, Punch, etc.
- **Public data**: Google Trends, Wine-Searcher, Vivino

## Base Scraper Classes

### DistributorScraper (Base Class)

```python
# app/scrapers/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import httpx


@dataclass
class RawProduct:
    """Raw product data from a distributor."""
    external_id: str
    name: str
    brand: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    volume_ml: Optional[int] = None
    abv: Optional[float] = None
    price: Optional[float] = None
    price_type: str = "wholesale"  # wholesale, retail, case, bottle
    inventory: Optional[int] = None
    in_stock: bool = True
    available_states: list[str] = None
    image_url: Optional[str] = None
    description: Optional[str] = None
    upc: Optional[str] = None
    url: Optional[str] = None
    raw_data: dict = None  # Original response data


@dataclass
class ScrapeResult:
    """Result of a scrape run."""
    success: bool
    source: str
    products: list[RawProduct]
    products_count: int
    errors: list[str]
    started_at: datetime
    completed_at: datetime
    metadata: dict = None


class BaseDistributorScraper(ABC):
    """
    Base class for all distributor scrapers.
    
    Each distributor scraper must implement:
    - authenticate(): Login and store session
    - get_products(): Fetch product catalog
    - get_categories(): List available categories (optional)
    """
    
    name: str = "base"
    base_url: str = ""
    
    def __init__(self, credentials: dict):
        """
        Initialize scraper with credentials.
        
        Args:
            credentials: Dict with auth info (email, password, etc.)
                        Loaded from environment or AWS Secrets Manager
        """
        self.credentials = credentials
        self.session = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/131.0.0.0 Safari/537.36"
            }
        )
        self.authenticated = False
        self.auth_cookies = {}
    
    @abstractmethod
    async def authenticate(self) -> bool:
        """
        Authenticate with the distributor.
        
        Returns:
            True if authentication successful, False otherwise.
        """
        pass
    
    @abstractmethod
    async def get_products(
        self, 
        category: str = None, 
        limit: int = None,
        offset: int = 0
    ) -> list[RawProduct]:
        """
        Fetch products from the distributor.
        
        Args:
            category: Optional category filter
            limit: Max products to fetch
            offset: Pagination offset
            
        Returns:
            List of RawProduct objects
        """
        pass
    
    async def get_categories(self) -> list[dict]:
        """
        Get available product categories.
        Override in subclass if supported.
        """
        return []
    
    async def run(self, categories: list[str] = None) -> ScrapeResult:
        """
        Main entry point - runs full scrape.
        
        Args:
            categories: List of categories to scrape. If None, scrape all.
            
        Returns:
            ScrapeResult with all products and metadata
        """
        started_at = datetime.utcnow()
        all_products = []
        errors = []
        
        try:
            # Authenticate
            if not await self.authenticate():
                return ScrapeResult(
                    success=False,
                    source=self.name,
                    products=[],
                    products_count=0,
                    errors=["Authentication failed"],
                    started_at=started_at,
                    completed_at=datetime.utcnow()
                )
            
            # Get categories to scrape
            if categories is None:
                available_cats = await self.get_categories()
                categories = [c.get("id") or c.get("slug") for c in available_cats]
            
            # If no categories defined, do a single scrape
            if not categories:
                categories = [None]
            
            # Scrape each category
            for category in categories:
                try:
                    products = await self.get_products(category=category)
                    all_products.extend(products)
                except Exception as e:
                    errors.append(f"Error scraping {category}: {str(e)}")
            
            return ScrapeResult(
                success=len(errors) == 0,
                source=self.name,
                products=all_products,
                products_count=len(all_products),
                errors=errors,
                started_at=started_at,
                completed_at=datetime.utcnow(),
                metadata={"categories_scraped": len(categories)}
            )
            
        except Exception as e:
            return ScrapeResult(
                success=False,
                source=self.name,
                products=all_products,
                products_count=len(all_products),
                errors=[str(e)],
                started_at=started_at,
                completed_at=datetime.utcnow()
            )
        
        finally:
            await self.session.aclose()
    
    async def _request(
        self, 
        method: str, 
        url: str, 
        **kwargs
    ) -> httpx.Response:
        """
        Make an authenticated request with retry logic.
        """
        import asyncio
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = await self.session.request(method, url, **kwargs)
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    # Session expired, re-authenticate
                    await self.authenticate()
                elif e.response.status_code == 429:
                    # Rate limited, wait and retry
                    await asyncio.sleep(30 * (attempt + 1))
                else:
                    raise
            except httpx.RequestError:
                if attempt < max_retries - 1:
                    await asyncio.sleep(5 * (attempt + 1))
                else:
                    raise
        
        raise Exception(f"Failed after {max_retries} retries")
```

## LibDib Scraper Implementation

```python
# app/scrapers/distributors/libdib.py

import asyncio
import random
from typing import Optional
from ..base import BaseDistributorScraper, RawProduct


class LibDibScraper(BaseDistributorScraper):
    """
    Scraper for LibDib distributor portal.
    
    API discovered endpoints:
    - POST /api/v1/offering/query/?format=json - Get product IDs
    - POST /api/v1/offering/query_digest/?format=json - Get product details
    - GET /api/v1/userAccount/?format=json - Account info
    """
    
    name = "libdib"
    base_url = "https://app.libdib.com"
    
    # Categories to scrape
    CATEGORIES = [
        {"name": "vodka", "filter": "spirits$spirits|type|vodka"},
        {"name": "whiskey", "filter": "spirits$spirits|type|whiskey"},
        {"name": "gin", "filter": "spirits$spirits|type|gin"},
        {"name": "rum", "filter": "spirits$spirits|type|rum"},
        {"name": "tequila", "filter": "spirits$spirits|type|tequila"},
        {"name": "mezcal", "filter": "spirits$spirits|type|mezcal"},
        {"name": "brandy", "filter": "spirits$spirits|type|brandy"},
        {"name": "liqueur", "filter": "spirits$spirits|type|liqueur"},
        {"name": "red_wine", "filter": "wine$wine|type|red"},
        {"name": "white_wine", "filter": "wine$wine|type|white"},
        {"name": "rose_wine", "filter": "wine$wine|type|rose"},
        {"name": "sparkling", "filter": "wine$wine|type|sparkling"},
        {"name": "rtd", "filter": "rtd$rtd"},
    ]
    
    def __init__(self, credentials: dict):
        """
        Args:
            credentials: {
                "email": str,
                "password": str,
                "session_id": str (optional, for pre-auth),
                "csrf_token": str (optional),
                "entity_slug": str (e.g., "weshipexpress")
            }
        """
        super().__init__(credentials)
        self.entity_slug = credentials.get("entity_slug", "")
        self.csrf_token = credentials.get("csrf_token", "")
    
    async def authenticate(self) -> bool:
        """
        Authenticate with LibDib.
        
        If session_id provided in credentials, use that.
        Otherwise, would need Playwright for full login flow.
        """
        session_id = self.credentials.get("session_id")
        csrf_token = self.credentials.get("csrf_token")
        
        if session_id and csrf_token:
            # Use provided session
            self.session.cookies.set("sessionid", session_id, domain="app.libdib.com")
            self.session.cookies.set("csrftoken", csrf_token, domain="app.libdib.com")
            self.csrf_token = csrf_token
            
            # Update headers
            self.session.headers.update({
                "X-CSRFToken": csrf_token,
                "Currententityslug": self.entity_slug,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Origin": self.base_url,
                "Referer": f"{self.base_url}/search/",
            })
            
            # Verify session is valid
            try:
                response = await self.session.get(
                    f"{self.base_url}/api/v1/userAccount/?format=json"
                )
                if response.status_code == 200:
                    self.authenticated = True
                    return True
            except Exception:
                pass
        
        # If no valid session, need to do full login via Playwright
        # This should be handled by SessionManager
        return False
    
    async def get_categories(self) -> list[dict]:
        """Return predefined categories."""
        return self.CATEGORIES
    
    async def get_products(
        self, 
        category: str = None,
        limit: int = None,
        offset: int = 0
    ) -> list[RawProduct]:
        """
        Fetch products for a category.
        
        Args:
            category: Category filter string (e.g., "spirits$spirits|type|vodka")
            limit: Max products (None = all)
            offset: Starting offset
        """
        if not self.authenticated:
            raise Exception("Not authenticated")
        
        all_products = []
        page_limit = 100
        current_offset = offset
        
        while True:
            # Step 1: Get product IDs
            query_payload = {
                "hashKey": f"?f={category}&nav=1" if category else "?nav=1",
                "limit": page_limit,
                "offset": current_offset,
                "order_by": "default",
                "storeViewType": "product"
            }
            
            response = await self._request(
                "POST",
                f"{self.base_url}/api/v1/offering/query/?format=json",
                json=query_payload
            )
            
            query_data = response.json()
            
            # Extract product IDs
            product_ids = []
            if "objects" in query_data:
                product_ids = [
                    obj.get("id") or obj.get("pk") 
                    for obj in query_data["objects"]
                    if obj.get("id") or obj.get("pk")
                ]
            
            if not product_ids:
                break
            
            # Step 2: Get product details
            import time
            digest_payload = {
                "fetch": [[pid, time.time()] for pid in product_ids],
                "hashKey": f"?f={category}&nav=1" if category else "?nav=1",
                "order_by": "default",
                "storeViewType": "product"
            }
            
            response = await self._request(
                "POST",
                f"{self.base_url}/api/v1/offering/query_digest/?format=json",
                json=digest_payload
            )
            
            digest_data = response.json()
            
            # Parse products
            products_data = digest_data.get("objects", [])
            for p in products_data:
                product = self._parse_product(p, category)
                if product:
                    all_products.append(product)
            
            # Check pagination
            total_count = query_data.get("total_count", 0)
            if limit and len(all_products) >= limit:
                break
            if current_offset + page_limit >= total_count:
                break
            if len(product_ids) < page_limit:
                break
            
            current_offset += page_limit
            
            # Polite delay
            await asyncio.sleep(random.uniform(1, 2))
        
        return all_products[:limit] if limit else all_products
    
    def _parse_product(self, data: dict, category: str = None) -> Optional[RawProduct]:
        """Parse LibDib API response into RawProduct."""
        try:
            # Extract volume from various possible fields
            volume_ml = None
            if data.get("volume"):
                volume_ml = int(data["volume"])
            elif data.get("sub_container_volume"):
                volume_ml = int(data["sub_container_volume"])
            
            return RawProduct(
                external_id=str(data.get("id") or data.get("pk") or data.get("slug")),
                name=data.get("name") or data.get("product_name", "Unknown"),
                brand=data.get("brand") or data.get("producer"),
                category=category.split("$")[0] if category and "$" in category else None,
                subcategory=category.split("|")[-1] if category and "|" in category else None,
                volume_ml=volume_ml,
                abv=float(data["abv"]) if data.get("abv") else None,
                price=float(data["seller_price"]) if data.get("seller_price") else None,
                price_type="wholesale",
                inventory=int(data["total_inventory"]) if data.get("total_inventory") else None,
                in_stock=bool(data.get("total_inventory", 0) > 0),
                available_states=data.get("sold_in_states", "").split(",") if data.get("sold_in_states") else None,
                image_url=data.get("image_url") or data.get("bottle_image"),
                description=data.get("story") or data.get("description"),
                upc=data.get("upc"),
                url=f"{self.base_url}/product/{data.get('slug')}" if data.get("slug") else None,
                raw_data=data
            )
        except Exception as e:
            # Log error but don't fail entire scrape
            print(f"Error parsing product: {e}")
            return None
```

## Session Manager

Handles authentication and session refresh across all scrapers.

```python
# app/scrapers/session_manager.py

import json
from datetime import datetime, timedelta
from typing import Optional
import boto3
from playwright.async_api import async_playwright


class SessionManager:
    """
    Manages authentication sessions for distributor scrapers.
    
    - Stores sessions in AWS Secrets Manager
    - Tracks expiration
    - Auto-refreshes via Playwright when expired
    """
    
    def __init__(self, use_aws: bool = True):
        self.use_aws = use_aws
        self.secrets_client = boto3.client('secretsmanager') if use_aws else None
        self._local_cache = {}
    
    async def get_session(self, distributor: str) -> dict:
        """
        Get valid session credentials for a distributor.
        Refreshes if expired.
        """
        secret_name = f"abvtrends/{distributor}"
        
        # Get current session
        session_data = await self._get_secret(secret_name)
        
        if not session_data:
            raise Exception(f"No credentials found for {distributor}")
        
        # Check if session is expired
        expires_at = session_data.get("expires_at")
        if expires_at:
            expires_dt = datetime.fromisoformat(expires_at)
            if datetime.utcnow() > expires_dt:
                # Session expired, refresh
                session_data = await self._refresh_session(distributor, session_data)
        
        return session_data
    
    async def _get_secret(self, secret_name: str) -> dict:
        """Get secret from AWS or local cache."""
        if self.use_aws:
            try:
                response = self.secrets_client.get_secret_value(SecretId=secret_name)
                return json.loads(response['SecretString'])
            except Exception:
                return None
        else:
            return self._local_cache.get(secret_name)
    
    async def _save_secret(self, secret_name: str, data: dict):
        """Save secret to AWS or local cache."""
        if self.use_aws:
            self.secrets_client.update_secret(
                SecretId=secret_name,
                SecretString=json.dumps(data)
            )
        else:
            self._local_cache[secret_name] = data
    
    async def _refresh_session(self, distributor: str, credentials: dict) -> dict:
        """
        Refresh session using Playwright.
        Logs in fresh and captures new cookies.
        """
        refresh_method = getattr(self, f"_refresh_{distributor}", None)
        if refresh_method:
            return await refresh_method(credentials)
        else:
            raise Exception(f"No refresh method for {distributor}")
    
    async def _refresh_libdib(self, credentials: dict) -> dict:
        """Refresh LibDib session via Playwright."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            
            try:
                # Navigate to login
                await page.goto("https://app.libdib.com/login")
                
                # Fill login form
                await page.fill('input[name="email"]', credentials["email"])
                await page.fill('input[name="password"]', credentials["password"])
                await page.click('button[type="submit"]')
                
                # Wait for redirect after login
                await page.wait_for_url("**/home/**", timeout=30000)
                
                # Extract cookies
                cookies = await context.cookies()
                session_id = next(
                    (c["value"] for c in cookies if c["name"] == "sessionid"), 
                    None
                )
                csrf_token = next(
                    (c["value"] for c in cookies if c["name"] == "csrftoken"), 
                    None
                )
                
                if not session_id or not csrf_token:
                    raise Exception("Failed to extract session cookies")
                
                # Update credentials
                new_creds = {
                    **credentials,
                    "session_id": session_id,
                    "csrf_token": csrf_token,
                    "expires_at": (datetime.utcnow() + timedelta(hours=12)).isoformat()
                }
                
                # Save to secrets
                await self._save_secret("abvtrends/libdib", new_creds)
                
                return new_creds
                
            finally:
                await browser.close()
```

## Celery Tasks

```python
# app/tasks/scrape_tasks.py

from celery import Celery
from datetime import datetime
import asyncio

from app.core.config import settings
from app.scrapers.session_manager import SessionManager
from app.scrapers.distributors.libdib import LibDibScraper
# ... other scrapers
from app.db.session import get_db
from app.services.product_matcher import ProductMatcher
from app.services.trend_scorer import TrendScorer


celery_app = Celery(
    "abvtrends",
    broker=settings.redis_url,
    backend=settings.redis_url
)

celery_app.conf.beat_schedule = {
    "scrape-distributors-hourly": {
        "task": "app.tasks.scrape_tasks.scrape_all_distributors",
        "schedule": 3600.0,  # Every hour
    },
    "scrape-media-hourly": {
        "task": "app.tasks.scrape_tasks.scrape_all_media",
        "schedule": 3600.0,
    },
    "calculate-trends": {
        "task": "app.tasks.scrape_tasks.calculate_all_trends",
        "schedule": 3600.0,
        "options": {"countdown": 600}  # Start 10 min after scrapes
    },
    "update-forecasts": {
        "task": "app.tasks.scrape_tasks.update_forecasts",
        "schedule": 3600.0,
        "options": {"countdown": 900}  # Start 15 min after scrapes
    },
}


DISTRIBUTOR_SCRAPERS = {
    "libdib": LibDibScraper,
    # "sgws": SGWSScraper,
    # "rndc": RNDCScraper,
    # ... add more as implemented
}


@celery_app.task
def scrape_all_distributors():
    """Run all distributor scrapers."""
    asyncio.run(_scrape_all_distributors())


async def _scrape_all_distributors():
    session_manager = SessionManager()
    
    for name, scraper_class in DISTRIBUTOR_SCRAPERS.items():
        try:
            # Get credentials
            credentials = await session_manager.get_session(name)
            
            # Initialize and run scraper
            scraper = scraper_class(credentials)
            result = await scraper.run()
            
            # Store results
            await _store_scrape_result(result)
            
        except Exception as e:
            print(f"Error scraping {name}: {e}")
            # Log to scrape_errors table
            await _log_scrape_error(name, e)


@celery_app.task
def scrape_distributor(distributor_name: str):
    """Run a single distributor scraper."""
    asyncio.run(_scrape_distributor(distributor_name))


async def _scrape_distributor(distributor_name: str):
    scraper_class = DISTRIBUTOR_SCRAPERS.get(distributor_name)
    if not scraper_class:
        raise ValueError(f"Unknown distributor: {distributor_name}")
    
    session_manager = SessionManager()
    credentials = await session_manager.get_session(distributor_name)
    
    scraper = scraper_class(credentials)
    result = await scraper.run()
    
    await _store_scrape_result(result)
    return result


@celery_app.task
def calculate_all_trends():
    """Calculate trend scores for all products."""
    asyncio.run(_calculate_all_trends())


async def _calculate_all_trends():
    scorer = TrendScorer()
    await scorer.calculate_all()


@celery_app.task
def update_forecasts():
    """Update forecasts for top products."""
    asyncio.run(_update_forecasts())


async def _update_forecasts():
    from app.services.forecaster import Forecaster
    forecaster = Forecaster()
    await forecaster.update_top_products(limit=500)


async def _store_scrape_result(result):
    """Store scrape result in database."""
    # Implementation: insert into scrape_runs, raw_product_data tables
    pass


async def _log_scrape_error(source: str, error: Exception):
    """Log scrape error to database."""
    # Implementation: insert into scrape_errors table
    pass
```

## Adding a New Scraper

To add a new distributor scraper:

1. **Create scraper class** in `app/scrapers/distributors/{name}.py`

```python
from ..base import BaseDistributorScraper, RawProduct

class NewDistributorScraper(BaseDistributorScraper):
    name = "newdistributor"
    base_url = "https://portal.newdistributor.com"
    
    async def authenticate(self) -> bool:
        # Implement authentication
        pass
    
    async def get_products(self, category=None, limit=None, offset=0) -> list[RawProduct]:
        # Implement product fetching
        pass
```

2. **Add refresh method** to SessionManager

```python
async def _refresh_newdistributor(self, credentials: dict) -> dict:
    # Playwright login flow
    pass
```

3. **Register scraper** in tasks

```python
DISTRIBUTOR_SCRAPERS = {
    # ... existing
    "newdistributor": NewDistributorScraper,
}
```

4. **Add credentials** to AWS Secrets Manager

```json
{
    "email": "...",
    "password": "...",
    "entity_slug": "...",
    "session_id": null,
    "csrf_token": null,
    "expires_at": null
}
```

5. **Add distributor record** to database

```sql
INSERT INTO distributors (name, slug, scraper_class) 
VALUES ('New Distributor', 'newdistributor', 'NewDistributorScraper');
```
