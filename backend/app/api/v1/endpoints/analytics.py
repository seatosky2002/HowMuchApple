from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.analytics import (
    AnalyticsSummaryResponse,
    ListingsResponse,
    PlatformCompareResponse,
    PopularResponse,
    TrendingResponse,
)
from app.services import analytics as analytics_service

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/summary", response_model=AnalyticsSummaryResponse)
async def get_summary(
    sku_id: int = Query(...),
    emd_id: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    data = await analytics_service.get_summary(db, sku_id, emd_id)
    return AnalyticsSummaryResponse(**data)


@router.get("/listings", response_model=ListingsResponse)
async def get_listings(
    sku_id: int = Query(...),
    emd_id: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort: str = Query(default="price_asc", pattern="^(price_asc|price_desc|newest)$"),
    source: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    data = await analytics_service.get_listings(db, sku_id, emd_id, page, page_size, sort, source)
    from app.schemas.analytics import ListingItem
    data["listings"] = [ListingItem(**item) for item in data["listings"]]
    return ListingsResponse(**data)


@router.get("/trending", response_model=TrendingResponse)
async def get_trending(
    category_id: int | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
    direction: str = Query(default="both", pattern="^(drop|rise|both)$"),
    db: AsyncSession = Depends(get_db),
):
    items = await analytics_service.get_trending(db, category_id, limit, direction)
    from app.schemas.analytics import TrendingItem
    return TrendingResponse(trending=[TrendingItem(**i) for i in items])


@router.get("/popular", response_model=PopularResponse)
async def get_popular(
    category_id: int | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    items = await analytics_service.get_popular(db, category_id, limit)
    from app.schemas.analytics import PopularItem
    return PopularResponse(popular=[PopularItem(**i) for i in items])


@router.get("/platform-compare", response_model=PlatformCompareResponse)
async def get_platform_compare(
    sku_id: int = Query(...),
    emd_id: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    platforms = await analytics_service.get_platform_compare(db, sku_id, emd_id)
    from app.schemas.analytics import PlatformPriceItem
    return PlatformCompareResponse(sku_id=sku_id, platforms=[PlatformPriceItem(**p) for p in platforms])
