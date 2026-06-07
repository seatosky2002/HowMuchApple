from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.crawler import CrawlerLog
from app.db.models.item import Item
from app.db.models.sku import SKU
from app.db.session import get_db
from app.schemas.stats import PlatformStats, ServiceStatsResponse

router = APIRouter(prefix="/stats", tags=["Stats"])

PLATFORMS = ["daangn", "bunjang", "joongna"]


@router.get("", response_model=ServiceStatsResponse)
async def get_stats(db: AsyncSession = Depends(get_db)):
    total_listings = (await db.execute(select(func.count(Item.item_id)))).scalar_one()
    total_skus = (await db.execute(select(func.count(SKU.sku_id)))).scalar_one()

    platform_stats = {}
    overall_last = None

    for platform in PLATFORMS:
        listing_count = (
            await db.execute(select(func.count(Item.item_id)).where(Item.source == platform))
        ).scalar_one()

        log = (
            await db.execute(
                select(CrawlerLog)
                .where(CrawlerLog.platform == platform, CrawlerLog.status == "success")
                .order_by(CrawlerLog.finished_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

        last_at = log.finished_at if log else None
        platform_stats[platform] = PlatformStats(listing_count=listing_count, last_crawled_at=last_at)
        if last_at and (overall_last is None or last_at > overall_last):
            overall_last = last_at

    return ServiceStatsResponse(
        total_listings=total_listings,
        total_skus=total_skus,
        last_crawled_at=overall_last,
        platforms=platform_stats,
    )
