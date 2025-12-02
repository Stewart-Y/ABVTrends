"""
ABVTrends - Forecasts API Endpoints

REST API for ML-based trend forecasting.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.product import Product
from app.models.trend_score import Forecast, TrendScore
from app.schemas.trend_score import (
    ForecastListResponse,
    ForecastResponse,
    ForecastSummary,
    ProductForecast,
)
from app.services.forecast_engine import ForecastEngine

router = APIRouter(prefix="/forecasts", tags=["forecasts"])


@router.get("/{product_id}", response_model=ProductForecast)
async def get_product_forecast(
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get 7-day forecast for a specific product.

    Returns predicted trend scores with confidence intervals.
    """
    # Verify product exists
    product_result = await db.execute(
        select(Product).where(Product.id == product_id)
    )
    product = product_result.scalar_one_or_none()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Get current score
    score_result = await db.execute(
        select(TrendScore.score)
        .where(TrendScore.product_id == product_id)
        .order_by(TrendScore.calculated_at.desc())
        .limit(1)
    )
    current_score = score_result.scalar() or 50.0

    # Get existing forecasts
    engine = ForecastEngine(db)
    forecasts = await engine.get_product_forecast(product_id)

    if not forecasts:
        raise HTTPException(
            status_code=404,
            detail="No forecast available. Model may need training.",
        )

    return ProductForecast(
        product_id=product_id,
        product_name=product.name,
        current_score=current_score,
        forecasts=[ForecastResponse.model_validate(f) for f in forecasts],
        model_version=forecasts[0].model_version if forecasts else "unknown",
        generated_at=forecasts[0].created_at if forecasts else datetime.utcnow(),
    )


@router.post("/{product_id}/generate", response_model=ProductForecast)
async def generate_forecast(
    product_id: UUID,
    horizon_days: int = Query(7, ge=1, le=14),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate a new forecast for a product.

    This will use trained models to create predictions.
    Requires sufficient historical data.
    """
    # Verify product exists
    product_result = await db.execute(
        select(Product).where(Product.id == product_id)
    )
    product = product_result.scalar_one_or_none()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Get current score
    score_result = await db.execute(
        select(TrendScore.score)
        .where(TrendScore.product_id == product_id)
        .order_by(TrendScore.calculated_at.desc())
        .limit(1)
    )
    current_score = score_result.scalar() or 50.0

    # Generate forecast
    try:
        engine = ForecastEngine(db)
        forecasts = await engine.generate_forecast(product_id, horizon_days)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Could not generate forecast: {str(e)}",
        )

    return ProductForecast(
        product_id=product_id,
        product_name=product.name,
        current_score=current_score,
        forecasts=[ForecastResponse.model_validate(f) for f in forecasts],
        model_version=forecasts[0].model_version if forecasts else "unknown",
        generated_at=datetime.utcnow(),
    )


@router.get("/batch/summaries")
async def get_forecast_summaries(
    product_ids: str = Query(..., description="Comma-separated product UUIDs"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get forecast summaries for multiple products.

    Useful for dashboard widgets showing predicted trends.
    """
    # Parse product IDs
    try:
        ids = [UUID(pid.strip()) for pid in product_ids.split(",")]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid product ID format")

    if len(ids) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 products per request")

    summaries = []

    for product_id in ids:
        # Get product and current score
        product_result = await db.execute(
            select(Product.name)
            .where(Product.id == product_id)
        )
        product_name = product_result.scalar()

        if not product_name:
            continue

        score_result = await db.execute(
            select(TrendScore.score)
            .where(TrendScore.product_id == product_id)
            .order_by(TrendScore.calculated_at.desc())
            .limit(1)
        )
        current_score = score_result.scalar() or 50.0

        # Get 7-day forecast
        forecast_result = await db.execute(
            select(Forecast.predicted_score, Forecast.confidence_upper_80)
            .where(Forecast.product_id == product_id)
            .order_by(Forecast.forecast_date.desc())
            .limit(1)
        )
        forecast_row = forecast_result.first()

        if forecast_row:
            predicted_7d = forecast_row[0]
            confidence = 80.0  # Using 80% confidence interval
        else:
            predicted_7d = current_score
            confidence = 50.0

        # Determine trend direction
        if predicted_7d > current_score + 5:
            direction = "up"
        elif predicted_7d < current_score - 5:
            direction = "down"
        else:
            direction = "stable"

        summaries.append(
            ForecastSummary(
                product_id=product_id,
                product_name=product_name,
                current_score=current_score,
                predicted_score_7d=predicted_7d,
                trend_direction=direction,
                confidence=confidence,
            )
        )

    return {"data": summaries}


@router.post("/{product_id}/train")
async def train_forecast_model(
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Train ML models for a specific product.

    Requires at least 30 days of historical trend scores.
    This is typically done automatically but can be triggered manually.
    """
    # Verify product exists
    product_result = await db.execute(
        select(Product).where(Product.id == product_id)
    )
    if not product_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Product not found")

    try:
        engine = ForecastEngine(db)
        results = await engine.train_models(product_id)

        return {
            "status": "success",
            "product_id": str(product_id),
            "results": results,
        }
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Training failed: {str(e)}",
        )
