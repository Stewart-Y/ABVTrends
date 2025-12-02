"""
ABVTrends - Trends API Endpoints

REST API for trending products and trend scores.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.product import Product, ProductCategory
from app.models.trend_score import TrendScore
from app.schemas.product import PaginationMeta
from app.schemas.trend_score import (
    ComponentBreakdown,
    TopTrendsResponse,
    TrendFilter,
    TrendingListResponse,
    TrendingProduct,
    TrendPaginationMeta,
    TrendScoreHistory,
    TrendScoreResponse,
)
from app.services.trend_engine import TrendEngine

router = APIRouter(prefix="/trends", tags=["trends"])


# Demo data for when database is not available
DEMO_PRODUCTS = [
    {"id": str(uuid4()), "name": "Clase Azul Reposado", "brand": "Clase Azul", "category": "spirits", "subcategory": "tequila", "score": 94, "tier": "viral"},
    {"id": str(uuid4()), "name": "Blanton's Single Barrel", "brand": "Blanton's", "category": "spirits", "subcategory": "bourbon", "score": 92, "tier": "viral"},
    {"id": str(uuid4()), "name": "Casamigos Añejo", "brand": "Casamigos", "category": "spirits", "subcategory": "tequila", "score": 88, "tier": "trending"},
    {"id": str(uuid4()), "name": "Buffalo Trace Bourbon", "brand": "Buffalo Trace", "category": "spirits", "subcategory": "bourbon", "score": 85, "tier": "trending"},
    {"id": str(uuid4()), "name": "Hendrick's Gin", "brand": "Hendrick's", "category": "spirits", "subcategory": "gin", "score": 82, "tier": "trending"},
    {"id": str(uuid4()), "name": "High Noon Sun Sips", "brand": "High Noon", "category": "rtd", "subcategory": None, "score": 78, "tier": "trending"},
    {"id": str(uuid4()), "name": "Opus One 2019", "brand": "Opus One", "category": "wine", "subcategory": None, "score": 76, "tier": "trending"},
    {"id": str(uuid4()), "name": "Monkey 47 Gin", "brand": "Monkey 47", "category": "spirits", "subcategory": "gin", "score": 65, "tier": "emerging"},
    {"id": str(uuid4()), "name": "Athletic Brewing Free Wave", "brand": "Athletic Brewing", "category": "beer", "subcategory": None, "score": 62, "tier": "emerging"},
    {"id": str(uuid4()), "name": "Fortaleza Blanco", "brand": "Fortaleza", "category": "spirits", "subcategory": "tequila", "score": 58, "tier": "emerging"},
]


def _get_demo_trending_product(p: dict) -> TrendingProduct:
    return TrendingProduct(
        id=UUID(p["id"]),
        name=p["name"],
        brand=p["brand"],
        category=p["category"],
        subcategory=p["subcategory"],
        image_url=None,
        trend_score=p["score"],
        trend_tier=p["tier"],
        score_change_24h=round((p["score"] - 50) * 0.1, 1),
        score_change_7d=round((p["score"] - 50) * 0.3, 1),
        component_breakdown=ComponentBreakdown(
            media=min(100, p["score"] + 5),
            social=min(100, p["score"] - 3),
            retailer=min(100, p["score"] + 2),
            price=min(100, p["score"] - 8),
            search=min(100, p["score"] + 1),
            seasonal=min(100, p["score"] - 5),
        ),
    )


@router.get("", response_model=TrendingListResponse)
async def get_trending_products(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    category: Optional[str] = Query(None),
    min_score: Optional[float] = Query(None, ge=0, le=100),
    sort_by: str = Query("score", regex="^(score|change_24h|change_7d)$"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get paginated list of trending products.

    Query parameters:
    - page: Page number (default: 1)
    - per_page: Items per page (default: 20, max: 100)
    - category: Filter by category (spirits, wine, rtd, beer)
    - min_score: Minimum trend score (0-100)
    - sort_by: Sort field (score, change_24h, change_7d)
    """
    # Build subquery for latest scores
    latest_scores = (
        select(
            TrendScore.product_id,
            func.max(TrendScore.calculated_at).label("latest"),
        )
        .group_by(TrendScore.product_id)
        .subquery()
    )

    # Main query
    query = (
        select(Product, TrendScore)
        .join(TrendScore, Product.id == TrendScore.product_id)
        .join(
            latest_scores,
            (TrendScore.product_id == latest_scores.c.product_id)
            & (TrendScore.calculated_at == latest_scores.c.latest),
        )
    )

    # Apply filters
    if category:
        try:
            cat_enum = ProductCategory(category.lower())
            query = query.where(Product.category == cat_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid category: {category}")

    if min_score is not None:
        query = query.where(TrendScore.score >= min_score)

    # Get total count
    count_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar() or 0

    # Apply sorting and pagination
    query = query.order_by(TrendScore.score.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(query)
    rows = result.all()

    # Transform to response
    trending_products = []
    for product, score in rows:
        trending_products.append(
            TrendingProduct(
                id=product.id,
                name=product.name,
                brand=product.brand,
                category=product.category.value,
                subcategory=product.subcategory.value if product.subcategory else None,
                image_url=product.image_url,
                trend_score=score.score,
                trend_tier=score.trend_tier,
                score_change_24h=None,  # TODO: Calculate from history
                score_change_7d=None,
                component_breakdown=ComponentBreakdown(
                    media=score.media_score,
                    social=score.social_score,
                    retailer=score.retailer_score,
                    price=score.price_score,
                    search=score.search_score,
                    seasonal=score.seasonal_score,
                ),
            )
        )

    return TrendingListResponse(
        data=trending_products,
        meta=TrendPaginationMeta(page=page, per_page=per_page, total=total),
        generated_at=datetime.utcnow(),
    )


@router.get("/top", response_model=TopTrendsResponse)
async def get_top_trends(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Get top trending products by tier.

    Returns:
    - viral: Products with score >= 90 (up to 5)
    - trending: Products with score >= 70 (up to 10)
    - emerging: Products with score >= 50 (up to 10)
    """
    # Check if running in demo mode (no database)
    if not getattr(request.app.state, "db_available", True):
        viral = [_get_demo_trending_product(p) for p in DEMO_PRODUCTS if p["score"] >= 90]
        trending = [_get_demo_trending_product(p) for p in DEMO_PRODUCTS if 70 <= p["score"] < 90]
        emerging = [_get_demo_trending_product(p) for p in DEMO_PRODUCTS if 50 <= p["score"] < 70]
        return TopTrendsResponse(
            viral=viral,
            trending=trending,
            emerging=emerging,
            generated_at=datetime.utcnow(),
        )

    engine = TrendEngine(db)

    # Get viral products (score >= 90)
    viral_result = await engine.get_trending_products(limit=5, min_score=90)
    viral = [
        _to_trending_product(p, s) for p, s in viral_result
    ]

    # Get trending products (score >= 70)
    trending_result = await engine.get_trending_products(limit=10, min_score=70)
    trending = [
        _to_trending_product(p, s) for p, s in trending_result
        if s.score < 90  # Exclude viral
    ]

    # Get emerging products (score >= 50)
    emerging_result = await engine.get_trending_products(limit=10, min_score=50)
    emerging = [
        _to_trending_product(p, s) for p, s in emerging_result
        if s.score < 70  # Exclude trending
    ]

    return TopTrendsResponse(
        viral=viral,
        trending=trending,
        emerging=emerging,
        generated_at=datetime.utcnow(),
    )


@router.get("/{product_id}", response_model=TrendScoreResponse)
async def get_product_trend(
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get the current trend score for a specific product.
    """
    # Get latest score
    result = await db.execute(
        select(TrendScore)
        .where(TrendScore.product_id == product_id)
        .order_by(TrendScore.calculated_at.desc())
        .limit(1)
    )
    score = result.scalar_one_or_none()

    if not score:
        raise HTTPException(status_code=404, detail="Trend score not found")

    return TrendScoreResponse.model_validate(score)


@router.get("/{product_id}/history", response_model=TrendScoreHistory)
async def get_trend_history(
    product_id: UUID,
    days: int = Query(30, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
):
    """
    Get trend score history for a product.

    Query parameters:
    - days: Number of days of history (default: 30, max: 90)
    """
    # Get product
    product_result = await db.execute(
        select(Product).where(Product.id == product_id)
    )
    product = product_result.scalar_one_or_none()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Get score history
    engine = TrendEngine(db)
    scores = await engine.get_score_history(product_id, days)

    return TrendScoreHistory(
        product_id=product_id,
        product_name=product.name,
        scores=[TrendScoreResponse.model_validate(s) for s in scores],
        period_start=datetime.utcnow(),
        period_end=datetime.utcnow(),
    )


@router.post("/{product_id}/recalculate", response_model=TrendScoreResponse)
async def recalculate_trend(
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Force recalculation of trend score for a product.

    Use sparingly - scores are calculated automatically.
    """
    # Verify product exists
    product_result = await db.execute(
        select(Product).where(Product.id == product_id)
    )
    if not product_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Product not found")

    engine = TrendEngine(db)
    score = await engine.calculate_score(product_id)

    return TrendScoreResponse.model_validate(score)


def _to_trending_product(product: Product, score: TrendScore) -> TrendingProduct:
    """Convert Product and TrendScore to TrendingProduct schema."""
    return TrendingProduct(
        id=product.id,
        name=product.name,
        brand=product.brand,
        category=product.category.value,
        subcategory=product.subcategory.value if product.subcategory else None,
        image_url=product.image_url,
        trend_score=score.score,
        trend_tier=score.trend_tier,
        score_change_24h=None,
        score_change_7d=None,
        component_breakdown=ComponentBreakdown(
            media=score.media_score,
            social=score.social_score,
            retailer=score.retailer_score,
            price=score.price_score,
            search=score.search_score,
            seasonal=score.seasonal_score,
        ),
    )
