"""
ABVTrends - Signals API Endpoints

REST API for signal management (mostly internal/admin use).
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.signal import Signal, SignalType
from app.models.source import Source
from app.schemas.signal import (
    SignalCreate,
    SignalFilter,
    SignalListResponse,
    SignalPaginationMeta,
    SignalResponse,
    SignalStats,
)

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("", response_model=SignalListResponse)
async def list_signals(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    signal_type: Optional[str] = Query(None),
    product_id: Optional[UUID] = Query(None),
    source_id: Optional[UUID] = Query(None),
    processed: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """
    List signals with filtering and pagination.

    Query parameters:
    - signal_type: Filter by signal type
    - product_id: Filter by product
    - source_id: Filter by source
    - processed: Filter by processed status
    """
    query = select(Signal).order_by(Signal.captured_at.desc())

    # Apply filters
    if signal_type:
        try:
            type_enum = SignalType(signal_type)
            query = query.where(Signal.signal_type == type_enum)
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Invalid signal type: {signal_type}"
            )

    if product_id:
        query = query.where(Signal.product_id == product_id)

    if source_id:
        query = query.where(Signal.source_id == source_id)

    if processed is not None:
        query = query.where(Signal.processed == processed)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    # Paginate
    query = query.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(query)
    signals = result.scalars().all()

    return SignalListResponse(
        data=[SignalResponse.model_validate(s) for s in signals],
        meta=SignalPaginationMeta(page=page, per_page=per_page, total=total),
    )


@router.get("/stats", response_model=SignalStats)
async def get_signal_stats(
    db: AsyncSession = Depends(get_db),
):
    """
    Get statistics about signals.
    """
    # Total signals
    total_result = await db.execute(select(func.count(Signal.id)))
    total_signals = total_result.scalar() or 0

    # Unprocessed count
    unprocessed_result = await db.execute(
        select(func.count(Signal.id)).where(Signal.processed == False)  # noqa: E712
    )
    unprocessed_count = unprocessed_result.scalar() or 0

    # Signals by type
    type_result = await db.execute(
        select(Signal.signal_type, func.count(Signal.id))
        .group_by(Signal.signal_type)
    )
    signals_by_type = {row[0].value: row[1] for row in type_result.all()}

    # Signals in last 24 hours
    from datetime import timedelta
    day_ago = datetime.utcnow() - timedelta(hours=24)
    day_result = await db.execute(
        select(func.count(Signal.id)).where(Signal.captured_at >= day_ago)
    )
    signals_last_24h = day_result.scalar() or 0

    # Signals in last 7 days
    week_ago = datetime.utcnow() - timedelta(days=7)
    week_result = await db.execute(
        select(func.count(Signal.id)).where(Signal.captured_at >= week_ago)
    )
    signals_last_7d = week_result.scalar() or 0

    return SignalStats(
        total_signals=total_signals,
        unprocessed_count=unprocessed_count,
        signals_by_type=signals_by_type,
        signals_last_24h=signals_last_24h,
        signals_last_7d=signals_last_7d,
    )


@router.get("/{signal_id}", response_model=SignalResponse)
async def get_signal(
    signal_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific signal by ID.
    """
    result = await db.execute(select(Signal).where(Signal.id == signal_id))
    signal = result.scalar_one_or_none()

    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")

    return SignalResponse.model_validate(signal)


@router.post("", response_model=SignalResponse, status_code=201)
async def create_signal(
    signal_data: SignalCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new signal.

    This is typically used internally by scrapers, but can be used
    for manual signal injection.
    """
    signal = Signal(
        product_id=signal_data.product_id,
        source_id=signal_data.source_id,
        signal_type=signal_data.signal_type,
        raw_data=signal_data.raw_data,
        url=signal_data.url,
        title=signal_data.title,
        sentiment_score=signal_data.sentiment_score,
        captured_at=signal_data.captured_at,
        processed=False,
    )

    db.add(signal)
    await db.commit()
    await db.refresh(signal)

    return SignalResponse.model_validate(signal)


@router.get("/types/list")
async def list_signal_types():
    """
    List all available signal types.
    """
    return {
        "signal_types": [
            {
                "value": t.value,
                "category": _get_signal_category(t),
            }
            for t in SignalType
        ]
    }


@router.get("/sources/list")
async def list_sources(
    db: AsyncSession = Depends(get_db),
):
    """
    List all configured sources.
    """
    result = await db.execute(
        select(Source).order_by(Source.tier, Source.name)
    )
    sources = result.scalars().all()

    return {
        "sources": [
            {
                "id": str(s.id),
                "name": s.name,
                "slug": s.slug,
                "tier": s.tier.value,
                "type": s.source_type.value,
                "is_active": s.is_active,
                "last_scraped": s.last_scraped_at.isoformat() if s.last_scraped_at else None,
                "total_signals": s.total_signals,
            }
            for s in sources
        ]
    }


def _get_signal_category(signal_type: SignalType) -> str:
    """Get category for a signal type."""
    media_types = {
        SignalType.MEDIA_MENTION,
        SignalType.ARTICLE_FEATURE,
        SignalType.AWARD_MENTION,
    }
    retailer_types = {
        SignalType.NEW_SKU,
        SignalType.PRICE_CHANGE,
        SignalType.PRICE_DROP,
        SignalType.PRICE_INCREASE,
        SignalType.OUT_OF_STOCK,
        SignalType.BACK_IN_STOCK,
        SignalType.PROMOTION,
    }
    social_types = {
        SignalType.SOCIAL_MENTION,
        SignalType.INFLUENCER_POST,
        SignalType.VIRAL_CONTENT,
    }

    if signal_type in media_types:
        return "media"
    elif signal_type in retailer_types:
        return "retailer"
    elif signal_type in social_types:
        return "social"
    else:
        return "search"
