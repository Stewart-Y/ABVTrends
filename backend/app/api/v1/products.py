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
