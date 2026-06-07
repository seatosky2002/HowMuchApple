import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.crawler import CrawlerLog
from app.db.models.item import Item, ItemStatus
from app.db.models.region import EMD, SGG, SD

logger = logging.getLogger(__name__)


class CrawledItem:
    __slots__ = ("title", "price", "url", "external_id", "source", "region_name", "sku_id", "category_id")

    def __init__(
        self,
        title: str,
        price: int,
        url: str,
        external_id: str,
        source: str,
        region_name: str = "",
        sku_id: int | None = None,
        category_id: int | None = None,
    ):
        self.title = title
        self.price = price
        self.url = url
        self.external_id = external_id
        self.source = source
        self.region_name = region_name
        self.sku_id = sku_id
        self.category_id = category_id


class BaseCrawler(ABC):
    platform: str = ""

    @abstractmethod
    async def crawl(self) -> list[CrawledItem]:
        """플랫폼에서 매물 목록을 크롤링해 반환."""

    async def run(self, db: AsyncSession) -> int:
        log = CrawlerLog(platform=self.platform, status="running", started_at=datetime.now(timezone.utc))
        db.add(log)
        await db.commit()

        start = datetime.now(timezone.utc)
        try:
            items = await self.crawl()
            count = await self._upsert(db, items)
            elapsed = int((datetime.now(timezone.utc) - start).total_seconds())

            log.status = "success"
            log.items_upserted = count
            log.duration_sec = elapsed
            log.finished_at = datetime.now(timezone.utc)
            await db.commit()

            logger.info("[%s] 완료 — %d개 upsert, %ds", self.platform, count, elapsed)
            return count
        except Exception as e:
            elapsed = int((datetime.now(timezone.utc) - start).total_seconds())
            log.status = "fail"
            log.error = str(e)[:500]
            log.duration_sec = elapsed
            log.finished_at = datetime.now(timezone.utc)
            await db.commit()
            logger.error("[%s] 실패: %s", self.platform, e)
            raise

    async def _upsert(self, db: AsyncSession, items: list[CrawledItem]) -> int:
        count = 0
        for crawled in items:
            region_id = await self._resolve_region(db, crawled.region_name)
            result = await db.execute(
                select(Item).where(Item.source == self.platform, Item.external_id == crawled.external_id)
            )
            existing = result.scalar_one_or_none()

            if existing:
                existing.price = crawled.price
                existing.title = crawled.title
                existing.status = ItemStatus.active
            else:
                new_item = Item(
                    sku_id=crawled.sku_id,
                    region_id=region_id,
                    category_id=crawled.category_id,
                    title=crawled.title,
                    price=crawled.price,
                    url=crawled.url,
                    source=self.platform,
                    external_id=crawled.external_id,
                )
                db.add(new_item)
                count += 1

        await db.commit()
        return count

    async def _resolve_region(self, db: AsyncSession, region_text: str) -> int | None:
        if not region_text:
            return None

        parts = region_text.strip().split()
        if len(parts) < 2:
            return None

        sd_name = parts[0]
        sgg_name = parts[1]
        emd_name = parts[2] if len(parts) > 2 else None

        sd = (await db.execute(select(SD).where(SD.name == sd_name))).scalar_one_or_none()
        if not sd:
            return None

        sgg = (await db.execute(select(SGG).where(SGG.sd_id == sd.sd_id, SGG.name == sgg_name))).scalar_one_or_none()
        if not sgg:
            return None

        if emd_name:
            emd = (await db.execute(select(EMD).where(EMD.sgg_id == sgg.sgg_id, EMD.name == emd_name))).scalar_one_or_none()
            return emd.region_id if emd else None

        emd = (await db.execute(select(EMD).where(EMD.sgg_id == sgg.sgg_id).limit(1))).scalar_one_or_none()
        return emd.region_id if emd else None


async def run_all_crawlers(db: AsyncSession) -> None:
    from app.crawlers.daangn import DaangnCrawler
    from app.crawlers.bunjang import BunjangCrawler
    from app.crawlers.joongna import JoognaCrawler

    for crawler_cls in (DaangnCrawler, BunjangCrawler, JoognaCrawler):
        try:
            await crawler_cls().run(db)
        except Exception as e:
            logger.error("크롤러 %s 실패 (계속 진행): %s", crawler_cls.platform, e)


async def run_crawler_by_platform(platform: str, db: AsyncSession) -> None:
    from app.crawlers.daangn import DaangnCrawler
    from app.crawlers.bunjang import BunjangCrawler
    from app.crawlers.joongna import JoognaCrawler

    mapping = {
        "daangn": DaangnCrawler,
        "bunjang": BunjangCrawler,
        "joongna": JoognaCrawler,
    }
    cls = mapping.get(platform)
    if cls:
        await cls().run(db)
