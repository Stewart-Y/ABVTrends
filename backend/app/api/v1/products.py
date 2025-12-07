"""
ABVTrends - Products API Endpoints

REST API for product management and details.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.product import Product, ProductCategory, ProductSubcategory
from app.models.signal import Signal
from app.models.trend_score import TrendScore
from app.schemas.product import (
    PaginationMeta,
    ProductCreate,
    ProductDetailResponse,
    ProductListResponse,
    ProductResponse,
    ProductUpdate,
    TrendScoreSummary,
)

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=ProductListResponse)
async def list_products(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    category: Optional[str] = Query(None),
    subcategory: Optional[str] = Query(None),
    brand: Optional[str] = Query(None),
    search: Optional[str] = Query(None, min_length=1, max_length=100),
    db: AsyncSession = Depends(get_db),
):
    """
    List all products with pagination and filters.

    Query parameters:
    - page: Page number (default: 1)
    - per_page: Items per page (default: 20, max: 100)
    - category: Filter by category
    - subcategory: Filter by subcategory
    - brand: Filter by brand name
    - search: Search by product name
    """
    query = select(Product)

    # Apply filters
    if category:
        try:
            cat_enum = ProductCategory(category.lower())
            query = query.where(Product.category == cat_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid category: {category}")

    if subcategory:
        try:
            sub_enum = ProductSubcategory(subcategory.lower())
            query = query.where(Product.subcategory == sub_enum)
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Invalid subcategory: {subcategory}"
            )

    if brand:
        query = query.where(Product.brand.ilike(f"%{brand}%"))

    if search:
        query = query.where(Product.name.ilike(f"%{search}%"))

    # Get total count
    count_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar() or 0

    # Apply pagination
    query = query.order_by(Product.name).offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(query)
    products = result.scalars().all()

    # Get latest scores for each product
    product_ids = [p.id for p in products]
    scores_result = await db.execute(
        select(TrendScore.product_id, TrendScore.score)
        .where(TrendScore.product_id.in_(product_ids))
        .distinct(TrendScore.product_id)
        .order_by(TrendScore.product_id, TrendScore.calculated_at.desc())
    )
    scores_map = {row[0]: row[1] for row in scores_result.all()}

    # Build response
    product_responses = []
    for product in products:
        response = ProductResponse.model_validate(product)
        response.latest_score = scores_map.get(product.id)
        product_responses.append(response)

    return ProductListResponse(
        data=product_responses,
        meta=PaginationMeta.create(page, per_page, total),
    )


@router.get("/{product_id}", response_model=ProductDetailResponse)
async def get_product(
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get detailed information about a specific product.

    Includes score history and signal count.
    """
    # Get product
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Get recent score history (last 30 days)
    scores_result = await db.execute(
        select(TrendScore.score, TrendScore.calculated_at)
        .where(TrendScore.product_id == product_id)
        .order_by(TrendScore.calculated_at.desc())
        .limit(30)
    )
    scores = [
        TrendScoreSummary(score=row[0], calculated_at=row[1])
        for row in scores_result.all()
    ]

    # Get signal count
    signal_count_result = await db.execute(
        select(func.count(Signal.id)).where(Signal.product_id == product_id)
    )
    signal_count = signal_count_result.scalar() or 0

    response = ProductDetailResponse.model_validate(product)
    response.score_history = scores
    response.signal_count = signal_count
    response.latest_score = scores[0].score if scores else None

    return response


@router.post("", response_model=ProductResponse, status_code=201)
async def create_product(
    product_data: ProductCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new product.

    Products are usually created automatically from signals,
    but this allows manual creation.
    """
    product = Product(
        name=product_data.name,
        brand=product_data.brand,
        category=product_data.category,
        subcategory=product_data.subcategory,
        description=product_data.description,
        image_url=str(product_data.image_url) if product_data.image_url else None,
    )

    db.add(product)
    await db.commit()
    await db.refresh(product)

    return ProductResponse.model_validate(product)


@router.patch("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: UUID,
    product_data: ProductUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Update a product.
    """
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Update fields
    update_data = product_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "image_url" and value:
            value = str(value)
        setattr(product, field, value)

    await db.commit()
    await db.refresh(product)

    return ProductResponse.model_validate(product)


@router.delete("/{product_id}", status_code=204)
async def delete_product(
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a product.

    This also deletes associated signals and trend scores (cascade).
    """
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    await db.delete(product)
    await db.commit()


@router.get("/{product_id}/signals")
async def get_product_signals(
    product_id: UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Get signals for a specific product.
    """
    # Verify product exists
    product_result = await db.execute(
        select(Product).where(Product.id == product_id)
    )
    if not product_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Product not found")

    # Get signals
    query = (
        select(Signal)
        .where(Signal.product_id == product_id)
        .order_by(Signal.captured_at.desc())
    )

    # Count
    count_result = await db.execute(
        select(func.count(Signal.id)).where(Signal.product_id == product_id)
    )
    total = count_result.scalar() or 0

    # Paginate
    query = query.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(query)
    signals = result.scalars().all()

    return {
        "data": [
            {
                "id": str(s.id),
                "signal_type": s.signal_type.value,
                "title": s.title,
                "url": s.url,
                "captured_at": s.captured_at.isoformat(),
                "source_id": str(s.source_id) if s.source_id else None,
            }
            for s in signals
        ],
        "meta": {"page": page, "per_page": per_page, "total": total},
    }


@router.get("/{product_id}/trend-summary")
async def get_product_trend_summary(
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get AI-generated trend summary for a product.

    Analyzes recent signals and generates an intelligent summary of why
    this product is trending.
    """
    # Get product
    product_result = await db.execute(
        select(Product).where(Product.id == product_id)
    )
    product = product_result.scalar_one_or_none()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Get recent signals (last 30 days)
    from datetime import datetime, timedelta
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)

    signals_result = await db.execute(
        select(Signal)
        .where(Signal.product_id == product_id)
        .where(Signal.captured_at >= thirty_days_ago)
        .order_by(Signal.captured_at.desc())
        .limit(50)
    )
    signals = signals_result.scalars().all()

    if not signals:
        return {
            "summary": f"{product.name} is a new product with limited data. More signals are being collected.",
            "key_points": [
                "Recently added to ABVTrends",
                "Data collection in progress",
                "Check back soon for trend insights"
            ],
            "signal_count": 0,
            "celebrity_affiliation": None,
            "launch_date": None,
            "region_focus": None,
            "trend_driver": "emerging"
        }

    # Analyze signals to build summary
    signal_types = {}
    sources = set()
    earliest_signal = signals[-1].captured_at
    latest_signal = signals[0].captured_at

    celebrity = None
    for signal in signals:
        signal_type = signal.signal_type.value
        signal_types[signal_type] = signal_types.get(signal_type, 0) + 1
        if signal.source_id:
            sources.add(signal.source_id)

        # Check for celebrity affiliation
        if signal.raw_data and isinstance(signal.raw_data, dict):
            celeb = signal.raw_data.get("celebrity_affiliation")
            if celeb:
                celebrity = celeb

    # Build key points
    key_points = []

    # Media coverage
    media_count = signal_types.get("media_mention", 0) + signal_types.get("article_feature", 0)
    if media_count > 0:
        key_points.append(f"Featured in {media_count} media publication{'s' if media_count != 1 else ''}")

    # Retailer presence
    retailer_count = signal_types.get("new_sku", 0)
    if retailer_count > 0:
        key_points.append(f"Available at {retailer_count} retailer{'s' if retailer_count != 1 else ''}")

    # Awards
    if "award_mention" in signal_types:
        key_points.append(f"Recognized with {signal_types['award_mention']} award{'s' if signal_types['award_mention'] != 1 else ''}")

    # Social mentions
    social_count = signal_types.get("social_mention", 0) + signal_types.get("influencer_post", 0)
    if social_count > 0:
        key_points.append(f"{social_count} social media mention{'s' if social_count != 1 else ''}")

    # Activity timeline
    if len(signals) > 10:
        key_points.append(f"High activity: {len(signals)} signals in last 30 days")

    # Build summary
    summary_parts = []
    summary_parts.append(f"{product.name}")
    if product.brand:
        summary_parts.append(f"by {product.brand}")

    # Determine trend driver
    trend_driver = "emerging"
    if celebrity:
        trend_driver = "celebrity_launch"
        summary_parts.append(f"has gained attention through its partnership with {celebrity}")
    elif media_count > 5:
        trend_driver = "media_buzz"
        summary_parts.append(f"is generating significant media buzz with coverage from {len(sources)} sources")
    elif "award_mention" in signal_types:
        trend_driver = "award_recognition"
        summary_parts.append(f"has received industry recognition and awards")
    elif retailer_count > 3:
        trend_driver = "retail_expansion"
        summary_parts.append(f"is expanding rapidly across major retailers")
    else:
        summary_parts.append(f"is an emerging {product.category} showing early momentum")

    summary_parts.append(f". The product has generated {len(signals)} trend signals in the past 30 days")

    if latest_signal and earliest_signal:
        days_active = (latest_signal - earliest_signal).days
        if days_active > 0:
            summary_parts.append(f", with consistent activity over {days_active} days")

    summary_parts.append(".")

    return {
        "summary": " ".join(summary_parts),
        "key_points": key_points if key_points else ["Limited trend data available"],
        "signal_count": len(signals),
        "celebrity_affiliation": celebrity,
        "launch_date": earliest_signal.isoformat() if earliest_signal else None,
        "region_focus": None,  # TODO: Extract from signal data
        "trend_driver": trend_driver,
        "days_active": (latest_signal - earliest_signal).days if latest_signal and earliest_signal else 0,
        "sources_count": len(sources)
    }


@router.get("/discover/new-arrivals")
async def get_new_arrivals(
    limit: int = Query(12, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """
    Get recently added products ("New to ABVTrends").

    Returns products ordered by creation date, showing the latest additions
    to the platform.
    """
    query = (
        select(Product)
        .order_by(Product.created_at.desc())
        .limit(limit)
    )

    result = await db.execute(query)
    products = result.scalars().all()

    # Get latest scores
    product_ids = [p.id for p in products]
    scores_result = await db.execute(
        select(TrendScore.product_id, TrendScore.score, TrendScore.trend_tier)
        .where(TrendScore.product_id.in_(product_ids))
        .distinct(TrendScore.product_id)
        .order_by(TrendScore.product_id, TrendScore.calculated_at.desc())
    )
    scores_map = {row[0]: {"score": row[1], "tier": row[2]} for row in scores_result.all()}

    return {
        "items": [
            {
                "id": str(p.id),
                "name": p.name,
                "brand": p.brand,
                "category": p.category.value,
                "image_url": p.image_url,
                "created_at": p.created_at.isoformat(),
                "score": scores_map.get(p.id, {}).get("score"),
                "trend_tier": scores_map.get(p.id, {}).get("tier").value if scores_map.get(p.id, {}).get("tier") else None,
            }
            for p in products
        ]
    }


@router.get("/discover/celebrity-bottles")
async def get_celebrity_bottles(
    limit: int = Query(12, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """
    Get products with celebrity affiliations.

    Searches signals for celebrity partnerships and returns products
    with the highest celebrity presence.
    """
    from datetime import datetime, timedelta

    # Find products with celebrity signals
    ninety_days_ago = datetime.utcnow() - timedelta(days=90)

    # Query for products that have signals with celebrity_affiliation in raw_data
    celebrity_query = (
        select(Signal.product_id, func.count(Signal.id).label("signal_count"))
        .where(Signal.captured_at >= ninety_days_ago)
        .where(Signal.raw_data.op("?")("celebrity_affiliation"))  # JSON has key
        .group_by(Signal.product_id)
        .order_by(func.count(Signal.id).desc())
        .limit(limit)
    )

    celeb_result = await db.execute(celebrity_query)
    celeb_products = celeb_result.all()

    if not celeb_products:
        return {"items": []}

    product_ids = [row[0] for row in celeb_products]

    # Get full product details
    products_result = await db.execute(
        select(Product).where(Product.id.in_(product_ids))
    )
    products = {p.id: p for p in products_result.scalars().all()}

    # Get latest scores
    scores_result = await db.execute(
        select(TrendScore.product_id, TrendScore.score, TrendScore.trend_tier)
        .where(TrendScore.product_id.in_(product_ids))
        .distinct(TrendScore.product_id)
        .order_by(TrendScore.product_id, TrendScore.calculated_at.desc())
    )
    scores_map = {row[0]: {"score": row[1], "tier": row[2]} for row in scores_result.all()}

    # Get celebrity names for each product
    celeb_names = {}
    for product_id in product_ids:
        signal_result = await db.execute(
            select(Signal.raw_data)
            .where(Signal.product_id == product_id)
            .where(Signal.raw_data.op("?")("celebrity_affiliation"))
            .limit(1)
        )
        signal_data = signal_result.scalar_one_or_none()
        if signal_data and isinstance(signal_data, dict):
            celeb_names[product_id] = signal_data.get("celebrity_affiliation")

    return {
        "items": [
            {
                "id": str(product_id),
                "name": products[product_id].name,
                "brand": products[product_id].brand,
                "category": products[product_id].category.value,
                "image_url": products[product_id].image_url,
                "score": scores_map.get(product_id, {}).get("score"),
                "trend_tier": scores_map.get(product_id, {}).get("tier").value if scores_map.get(product_id, {}).get("tier") else None,
                "celebrity_affiliation": celeb_names.get(product_id),
                "signal_count": dict(celeb_products)[product_id],
            }
            for product_id in product_ids
            if product_id in products
        ]
    }


@router.get("/discover/early-movers")
async def get_early_movers(
    limit: int = Query(12, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """
    Get products with emerging momentum ("Early Movers").

    Returns products in the "emerging" tier (50-69 score) that have shown
    high signal velocity in recent days.
    """
    from datetime import datetime, timedelta

    # Get products with recent high signal activity
    seven_days_ago = datetime.utcnow() - timedelta(days=7)

    # Find products with most signals in last 7 days
    signal_velocity_query = (
        select(Signal.product_id, func.count(Signal.id).label("recent_signals"))
        .where(Signal.captured_at >= seven_days_ago)
        .group_by(Signal.product_id)
        .order_by(func.count(Signal.id).desc())
        .limit(limit * 2)  # Get more candidates to filter by tier
    )

    velocity_result = await db.execute(signal_velocity_query)
    velocity_products = velocity_result.all()

    if not velocity_products:
        return {"items": []}

    product_ids = [row[0] for row in velocity_products]

    # Get products with their latest scores
    products_result = await db.execute(
        select(Product).where(Product.id.in_(product_ids))
    )
    products = {p.id: p for p in products_result.scalars().all()}

    # Get latest scores and filter by emerging tier
    scores_result = await db.execute(
        select(TrendScore.product_id, TrendScore.score, TrendScore.trend_tier)
        .where(TrendScore.product_id.in_(product_ids))
        .distinct(TrendScore.product_id)
        .order_by(TrendScore.product_id, TrendScore.calculated_at.desc())
    )

    # Build results, prioritizing emerging tier
    items = []
    for row in scores_result.all():
        product_id = row[0]
        score = row[1]
        tier = row[2]

        if product_id not in products:
            continue

        product = products[product_id]
        signal_count = dict(velocity_products).get(product_id, 0)

        # Prioritize emerging tier, but include trending as fallback
        items.append({
            "id": str(product_id),
            "name": product.name,
            "brand": product.brand,
            "category": product.category.value,
            "image_url": product.image_url,
            "score": score,
            "trend_tier": tier.value if tier else None,
            "recent_signal_count": signal_count,
            "is_emerging": tier.value == "emerging" if tier else False,
        })

    # Sort: emerging tier first, then by signal velocity
    items.sort(key=lambda x: (not x["is_emerging"], -x["recent_signal_count"]))

    return {"items": items[:limit]}


@router.get("/categories/list")
async def list_categories():
    """
    List all available product categories and subcategories.
    """
    return {
        "categories": [c.value for c in ProductCategory],
        "subcategories": {
            "spirits": [
                "whiskey", "bourbon", "scotch", "vodka", "gin",
                "rum", "tequila", "mezcal", "brandy", "cognac", "liqueur"
            ],
            "wine": [
                "red_wine", "white_wine", "rose", "sparkling",
                "champagne", "natural_wine", "orange_wine"
            ],
            "rtd": ["hard_seltzer", "canned_cocktail", "hard_kombucha"],
            "beer": ["craft_beer", "ipa", "lager", "stout"],
        },
    }
